import logging
import os
from collections import defaultdict

import pandas as pd

from config import (
    FIFA_DATE_COL, FIFA_MATCH_COL, FIFA_HOME_PLAYER_COL, FIFA_AWAY_PLAYER_COL, FIFA_HOME_SCORE_COL,
    FIFA_AWAY_SCORE_COL, FIFA_HOME_PENALTIES_SCORE_COL, FIFA_AWAY_PENALTIES_SCORE_COL, FIFA_HOME_STARS_COL,
    FIFA_AWAY_STARS_COL, FIFA_BASE_MMR, FIFA_BASE_MMR_DELTA, FIFA_BASE_UNCERTAINTY, FIFA_GAMMA, 
    FIFA_MMR_DECAY_FACTOR_PER_DAY, FIFA_UNCERTAINTY_INCREASE, FIFA_UNCERTAINTY_DECAY, 
    FIFA_GOAL_DIFFERENCE_FACTOR, FIFA_STAR_RATING_FACTOR, FIFA_MAX_DECAY, FIFA_MMR_RECLAIM,
    FIFA_ENGINE_LOG_FILE,
)
from gsheets import read_sheet_df
from engine.handlers import (
    UncertaintyHandler, FifaTeamMatchHandler, CappedDecayHandler, InflationHandler,
)
from engine.handlers.goal_difference_handler import FifaGoalDifferenceHandler
from engine.handlers.inactivity_handler import InactivityHandler
from utils import format_date, round_dict_values, sum_dicts, sum_default_dicts


INFLATION = False


def _setup_fifa_handler_logger() -> logging.Logger:
    logger = logging.getLogger("fifa_engine_handlers")
    if logger.handlers:
        return logger

    os.makedirs(os.path.dirname(FIFA_ENGINE_LOG_FILE), exist_ok=True)

    logger.setLevel(logging.INFO)
    logger.propagate = False

    file_handler = logging.FileHandler(FIFA_ENGINE_LOG_FILE, mode="w", encoding="utf-8")
    formatter = logging.Formatter("%(asctime)s | %(levelname)s | %(message)s")
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    return logger


def get_fifa_table(sheet_name: str) -> list:
    """
    Process FIFA matches and calculate MMR changes.
    
    table structure:
    {
        "Date": str,
        "Match": int,
        "Home Player": str,
        "Away Player": str,
        "Home Score": int,
        "Away Score": int,
        "Home Penalties Score": int,
        "Away Penalties Score": int,
        "Home team rating": float,
        "Away team rating": float,
        "Home Win Prob.": float,
        "Away Win Prob.": float,
        "Uncertainty Factors": {str: float},
        "Total Delta": {str: float},
        "Total MMR": {str: float}
    }
    """
    table = []
    
    # Initialize session state
    active_players = set()
    adjusted_mmrs = defaultdict(lambda: FIFA_BASE_MMR)
    raw_mmrs = defaultdict(lambda: FIFA_BASE_MMR)
    logger = _setup_fifa_handler_logger()

    logger.info("=== FIFA engine start | sheet=%s ===", sheet_name)

    # Initialize handlers
    team_match = FifaTeamMatchHandler(FIFA_BASE_MMR_DELTA, FIFA_GAMMA, FIFA_STAR_RATING_FACTOR, logger_name="fifa_engine_handlers")
    goal_diff = FifaGoalDifferenceHandler(FIFA_BASE_MMR_DELTA, FIFA_GOAL_DIFFERENCE_FACTOR, logger_name="fifa_engine_handlers")
    inactivity = InactivityHandler(logger_name="fifa_engine_handlers")
    uncertainty = UncertaintyHandler(FIFA_BASE_MMR_DELTA, FIFA_UNCERTAINTY_DECAY, FIFA_UNCERTAINTY_INCREASE, FIFA_BASE_UNCERTAINTY, logger_name="fifa_engine_handlers")
    decay = CappedDecayHandler(FIFA_MMR_DECAY_FACTOR_PER_DAY, FIFA_MMR_RECLAIM, FIFA_MAX_DECAY, logger_name="fifa_engine_handlers")
    inflation = InflationHandler(FIFA_BASE_MMR, logger_name="fifa_engine_handlers")

    for _, row in read_sheet_df(sheet_name).iterrows():
        # Extract match data
        date_val = pd.to_datetime(row[FIFA_DATE_COL])
        date_str = format_date(date_val)
        match_num = int(row[FIFA_MATCH_COL])
        home_player = row[FIFA_HOME_PLAYER_COL]
        away_player = row[FIFA_AWAY_PLAYER_COL]
        home_score = int(row[FIFA_HOME_SCORE_COL])
        away_score = int(row[FIFA_AWAY_SCORE_COL])
        home_penalties_score = int(row[FIFA_HOME_PENALTIES_SCORE_COL])
        away_penalties_score = int(row[FIFA_AWAY_PENALTIES_SCORE_COL])
        home_stars = float(row[FIFA_HOME_STARS_COL])
        away_stars = float(row[FIFA_AWAY_STARS_COL])

        logger.info(
            "MATCH_START | date=%s | match=%s | home=%s | away=%s | score=%s-%s",
            date_str, match_num, home_player, away_player, home_score, away_score,
        )

        # Process match outcome
        team_match.process_match_outcome(
            date_val, home_player, away_player, home_stars, away_stars,
            home_score, away_score, home_penalties_score, away_penalties_score,
            raw_mmrs)
        
        # Process goal difference
        goal_diff.process_goal_difference(
            home_player, away_player, home_score, away_score,
            home_penalties_score, away_penalties_score, team_match.get_match_deltas())
        
        # Process inactivity
        inactivity.process_inactivity(date_val, active_players)
        
        # Update active players
        active_players.update([home_player, away_player])

        # Process uncertainty
        uncertainty.process_uncertainty(
            sum_dicts([team_match.get_match_deltas(), goal_diff.get_goal_deltas()]),
            inactivity.get_inactivity_days())
        
        # Calculate total delta
        total_delta = sum_dicts([team_match.get_match_deltas(), goal_diff.get_goal_deltas(), 
                                 uncertainty.get_uncertainty_deltas()])

        # Update raw MMRs
        raw_mmrs = sum_default_dicts([raw_mmrs, total_delta])

        # Process decay
        decay.process_decay([home_player, away_player], uncertainty.get_inactivity_days(), adjusted_mmrs)

        # Update adjusted MMRs with total delta and decay
        adjusted_mmrs = sum_default_dicts([adjusted_mmrs, total_delta, decay.get_decay_adjustment_deltas()])

        # Process inflation
        if INFLATION:
            inflation.process_inflation(
                sum_dicts([uncertainty.get_uncertainty_deltas(), decay.get_decay_adjustment_deltas()]),
                active_players, adjusted_mmrs)

            # Final adjusted MMR update with inflation
            adjusted_mmrs = sum_default_dicts([adjusted_mmrs, inflation.get_inflation_adjustment_deltas()])

        logger.info(
            "MATCH_END | total_mmr=%s",
            {k: round(v, 3) for k, v in sorted(adjusted_mmrs.items())},
        )

        # Append match row to table
        table.append({
            "Date": date_str,
            "Match": match_num,
            "Home Player": home_player,
            "Away Player": away_player,
            "Home Score": home_score,
            "Away Score": away_score,
            "Home Penalties Score": home_penalties_score,
            "Away Penalties Score": away_penalties_score,
            "Home team rating": home_stars,
            "Away team rating": away_stars,
            "Home Win Prob.": round(team_match.get_win_prob()[0], 2),
            "Away Win Prob.": round(team_match.get_win_prob()[1], 2),
            "Uncertainty Factors": round_dict_values(uncertainty.get_uncertainty_factors().copy(), 2),
            "Total Delta": round_dict_values(sum_dicts([
                total_delta,
                inflation.get_inflation_adjustment_deltas().copy(),
                decay.get_decay_adjustment_deltas()])),
            "Total MMR": round_dict_values(adjusted_mmrs.copy()),
        })

    logger.info("=== FIFA engine end | sheet=%s | matches=%s ===", sheet_name, len(table))

    return table