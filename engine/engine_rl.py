import pandas as pd
import logging
import os
from collections import defaultdict 
from engine.handlers.inactivity_handler import InactivityHandler
from gsheets import read_sheet_df
from .handlers.team_match_handler import RLTeamMatchHandler
from .handlers.goal_difference_handler import RLGoalDifferenceHandler
from .handlers.uncertainty_handler import UncertaintyHandler
from .handlers.decay_handler import CappedDecayHandler
from .handlers.inflation_handler import InflationHandler
from utils import format_date, round_dict_values, convert_bool, sum_dicts, sum_default_dicts
from config import (
    RL_DATE_COL, RL_MATCH_COL, RL_BLUE_TEAM_COLS, RL_MAX_DECAY, RL_ORANGE_TEAM_COLS, RL_BLUE_SCORE_COL, 
    RL_ORANGE_SCORE_COL, RL_OVERTIME_COL,

    RL_BASE_MMR, RL_GAMMA, RL_K_FACTOR, RL_BASE_MMR_DELTA, RL_GOAL_DIFFERENCE_FACTOR, 
    RL_BASE_UNCERTAINTY, RL_UNCERTAINTY_DECAY, RL_UNCERTAINTY_INCREASE, RL_MMR_DECAY_FACTOR_PER_DAY, RL_MMR_RECLAIM,
    RL_ENGINE_LOG_FILE
)


def _setup_rl_handler_logger() -> logging.Logger:
    logger = logging.getLogger("rl_engine_handlers")
    if logger.handlers:
        return logger

    os.makedirs(os.path.dirname(RL_ENGINE_LOG_FILE), exist_ok=True)

    logger.setLevel(logging.INFO)
    logger.propagate = False

    file_handler = logging.FileHandler(RL_ENGINE_LOG_FILE, mode="w", encoding="utf-8")
    formatter = logging.Formatter("%(asctime)s | %(levelname)s | %(message)s")
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    return logger


def get_RL_table(sheet_name):
    # table structure:
    # {
    #   "Date": str,                            # Match date (es. "05-Mar-24")
    #   "Match": int,                           # Sequential match number
    #   "Blue Team": [str],                     # List of blue team players
    #   "Orange Team": [str],                   # List of orange team players
    #   "Blue Score": int,                      # Goals scored by the blue team
    #   "Orange Score": int,                    # Goals scored by the orange team
    #   "Overtime": bool,                       # True if the match went to overtime
    #   "Blue Win Prob.": float,                # Expected probability of blue team winning
    #   "Orange Win Prob.": float,              # Expected probability of orange team winning
    #   "Uncertainty Factors": {str: float},    # Uncertainty factors for each active player before the match
    #   "Total Delta": {str: int},              # Total MMR delta for each active player adjusted for inflation
    #   "Total MMR": {str: int},                # Total MMR before for each active player adjusted for inflation
    # }
    table = []
    
    # Initialize session state
    active_players = set()
    adjusted_mmrs = defaultdict(lambda: RL_BASE_MMR)
    raw_mmrs = defaultdict(lambda: RL_BASE_MMR)
    logger = _setup_rl_handler_logger()

    logger.info("=== RL engine start | sheet=%s ===", sheet_name)

    # Initialize handlers
    team_match = RLTeamMatchHandler(
        RL_BASE_MMR_DELTA, RL_GAMMA, RL_K_FACTOR, logger_name="rl_engine_handlers")
    goal_diff = RLGoalDifferenceHandler(
        RL_BASE_MMR_DELTA, RL_GOAL_DIFFERENCE_FACTOR[sheet_name], logger_name="rl_engine_handlers")
    inactivity = InactivityHandler(logger_name="rl_engine_handlers")
    uncertainty = UncertaintyHandler(
        RL_BASE_MMR_DELTA, RL_UNCERTAINTY_DECAY[sheet_name], RL_UNCERTAINTY_INCREASE, RL_BASE_UNCERTAINTY, logger_name="rl_engine_handlers")
    decay = CappedDecayHandler(
        RL_MMR_DECAY_FACTOR_PER_DAY, RL_MMR_RECLAIM, RL_MAX_DECAY, logger_name="rl_engine_handlers")
    inflation = InflationHandler(
        RL_BASE_MMR, logger_name="rl_engine_handlers")

    for _, rows in read_sheet_df(sheet_name).iterrows():
        # Extract match data
        date_val = pd.to_datetime(rows[RL_DATE_COL])
        date_str = format_date(date_val)
        match_num = int(rows[RL_MATCH_COL])
        blue_team = [p for p in rows[RL_BLUE_TEAM_COLS] if pd.notna(p)]
        orange_team = [p for p in rows[RL_ORANGE_TEAM_COLS] if pd.notna(p)]
        blue_score = rows[RL_BLUE_SCORE_COL]
        orange_score = rows[RL_ORANGE_SCORE_COL]
        overtime = convert_bool(rows[RL_OVERTIME_COL])

        logger.info(
            "MATCH_START | date=%s | match=%s | blue=%s | orange=%s | score=%s-%s | overtime=%s",
            date_str,
            match_num,
            blue_team,
            orange_team,
            blue_score,
            orange_score,
            overtime,
        )
        
        # raw_mmrs --> match_deltas
        team_match.process_match_outcome(
            date_val, blue_team, orange_team, blue_score, orange_score, overtime, 
            raw_mmrs)
        
        # match_deltas --> goal_difference_deltas
        goal_diff.process_goal_difference(
            blue_team, orange_team, blue_score, orange_score, overtime, 
            team_match.get_match_deltas())
        
        # active_players --> inactivity_days
        inactivity.process_inactivity(date_val, active_players)
        
        # active_players --> active_players
        active_players.update(blue_team + orange_team)

        # inactivity_days, match_deltas + goal_difference_deltas --> 
        # --> inactivity_days, uncertainty_deltas, uncertainty_factors
        uncertainty.process_uncertainty(
            sum_dicts([team_match.get_match_deltas(), goal_diff.get_goal_deltas()]),
            inactivity.get_inactivity_days()
            )
        
        # match_deltas + goal_difference_deltas + uncertainty_deltas --> total_delta
        total_delta = sum_dicts([team_match.get_match_deltas(), goal_diff.get_goal_deltas(), uncertainty.get_uncertainty_deltas()])

        # raw_mmrs + total_delta --> raw_mmrs
        raw_mmrs = sum_default_dicts([raw_mmrs, total_delta])

        # adjusted_mmrs, raw_mmrs --> decay_adjustment_deltas
        decay.process_decay(blue_team + orange_team, uncertainty.get_inactivity_days(), adjusted_mmrs)

        # adjusted_mmrs + total_delta + decay_adjustment_deltas --> adjusted_mmrs
        adjusted_mmrs = sum_default_dicts([adjusted_mmrs, total_delta, decay.get_decay_adjustment_deltas()])

        # uncertainty_deltas, decay_adjustment_deltas, active_players, adjusted_mmrs --> inflation_adjustment_deltas
        inflation.process_inflation(
            sum_dicts([uncertainty.get_uncertainty_deltas(), decay.get_decay_adjustment_deltas()]), 
            active_players, adjusted_mmrs)
        
        # adjusted_mmrs + inflation_adjustment_deltas --> adjusted_mmrs
        adjusted_mmrs = sum_default_dicts([adjusted_mmrs, inflation.get_inflation_adjustment_deltas()])
        logger.info(
            "MATCH_END | total_mmr=%s",
            {k: round(v, 3) for k, v in sorted(adjusted_mmrs.items())},
        )
        
        # Append match row to table (round all deltas and MMR to integers)
        table.append({
            "Date": date_str,
            "Match": match_num,
            "Blue Team": blue_team,
            "Orange Team": orange_team,
            "Blue Score": blue_score,
            "Orange Score": orange_score,
            "Overtime": overtime,
            "Blue Win Prob.": round(team_match.get_win_prob()[0], 2),
            "Orange Win Prob.": round(team_match.get_win_prob()[1], 2),
            "Uncertainty Factors": round_dict_values(uncertainty.get_uncertainty_factors().copy(), 2),
            "Total Delta": round_dict_values(sum_dicts([
                total_delta, 
                inflation.get_inflation_adjustment_deltas().copy(), 
                decay.get_decay_adjustment_deltas()])),
            "Total MMR": round_dict_values(adjusted_mmrs.copy()),
        })

    logger.info("=== RL engine end | sheet=%s | matches=%s ===", sheet_name, len(table))

    return table

