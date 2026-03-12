import pandas as pd
from collections import defaultdict 
from gsheets import read_sheet_df
from .handlers.team_match_handler import RLTeamMatchHandler
from .handlers.goal_difference_handler import RLGoalDifferenceHandler
from .handlers.uncertainty_handler import UncertaintyHandler
from .handlers.inactivity_handler import TsInactivityHandler
from .handlers.inflation_handler import InflationHandler
from utils import format_date, round_dict_values, convert_bool
from config import (
    RL_DATE_COL, RL_MATCH_COL, RL_BLUE_TEAM_COLS, RL_MAX_DECAY, RL_ORANGE_TEAM_COLS, RL_BLUE_SCORE_COL, 
    RL_ORANGE_SCORE_COL, RL_OVERTIME_COL,

    RL_BASE_MMR, RL_GAMMA, RL_K_FACTOR, RL_BASE_MMR_DELTA, RL_GOAL_DIFFERENCE_FACTOR, 
    RL_BASE_UNCERTAINTY, RL_UNCERTAINTY_DECAY, RL_UNCERTAINTY_INCREASE, RL_MMR_DECAY_FACTOR_PER_DAY, RL_MMR_RECLAIM 
)

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
    #   "Inflation Factor": float               # Multiplicative factor representing the total inflation applied to every MMR or delta
    # }
    table = []
    
    # Initialize shared state
    active_players = set()

    blue_win_prob = [0.0]
    orange_win_prob = [0.0]

    last_mmr = defaultdict(lambda: RL_BASE_MMR)
    last_date_mmr = defaultdict(lambda: RL_BASE_MMR)
    last_adjusted_mmr = defaultdict(lambda: RL_BASE_MMR)
    total_delta = defaultdict(float)

    uncertainty_factors = defaultdict(lambda: RL_BASE_UNCERTAINTY)
    pre_match_uncertainty_factors = defaultdict(lambda: RL_BASE_UNCERTAINTY)
    inactivity_days = defaultdict(int)
    decay_adjustments = defaultdict(float)

    total_inflation = [0.0]
    inflation_factor = [1.0]

    # Initialize handlers
    team_match = RLTeamMatchHandler(blue_win_prob, orange_win_prob, 
                                    last_mmr, last_date_mmr, total_delta, 
                                    RL_BASE_MMR_DELTA, RL_GAMMA, RL_K_FACTOR)
    goal_diff = RLGoalDifferenceHandler(last_mmr, total_delta, 
                                        RL_GOAL_DIFFERENCE_FACTOR[sheet_name])
    uncertainty = UncertaintyHandler(active_players, 
                                     last_mmr, last_date_mmr, total_delta, 
                                     uncertainty_factors, pre_match_uncertainty_factors, inactivity_days,
                                     total_inflation,
                                     RL_UNCERTAINTY_DECAY[sheet_name], RL_UNCERTAINTY_INCREASE, RL_BASE_UNCERTAINTY)
    inactivity = TsInactivityHandler(active_players,
                                     last_mmr, last_adjusted_mmr, total_delta,
                                     total_inflation,
                                     inactivity_days, decay_adjustments,
                                     RL_MMR_DECAY_FACTOR_PER_DAY, RL_MMR_RECLAIM, RL_MAX_DECAY)
    inflation = InflationHandler(active_players, 
                                 total_inflation, inflation_factor, total_delta, last_adjusted_mmr, 
                                 RL_BASE_MMR)

    for _, rows in read_sheet_df(sheet_name).iterrows():
        total_delta.clear()
        
        # Extract match data
        date_val = pd.to_datetime(rows[RL_DATE_COL])
        date_str = format_date(date_val)
        match_num = int(rows[RL_MATCH_COL])
        blue_team = [p for p in rows[RL_BLUE_TEAM_COLS] if pd.notna(p)]
        orange_team = [p for p in rows[RL_ORANGE_TEAM_COLS] if pd.notna(p)]
        blue_score = rows[RL_BLUE_SCORE_COL]
        orange_score = rows[RL_ORANGE_SCORE_COL]
        overtime = convert_bool(rows[RL_OVERTIME_COL])
        
        active_players.update(blue_team + orange_team)

        # Apply match outcome
        team_match.apply_match_outcome(blue_team, orange_team, [blue_score, orange_score], overtime)
        
        # Apply goal difference bonus/penalty
        goal_diff.apply_goal_difference(blue_team, orange_team, [blue_score, orange_score], overtime)

        # Process date change for uncertainty, apply uncertainty amplification and reduce uncertainty
        uncertainty.apply_uncertainty_amplification(blue_team + orange_team, date_val)

        # Apply inactivity effects
        inactivity.apply_inactivity_effects(blue_team + orange_team)

        # Apply inflation correction
        inflation.apply_inflation_correction()

        # Append match row to table (round all deltas and MMR to integers)
        table.append({
            "Date": date_str,
            "Match": match_num,
            "Blue Team": blue_team,
            "Orange Team": orange_team,
            "Blue Score": blue_score,
            "Orange Score": orange_score,
            "Overtime": overtime,
            "Blue Win Prob.": round(blue_win_prob[0], 2),
            "Orange Win Prob.": round(orange_win_prob[0], 2),
            "Uncertainty Factors": pre_match_uncertainty_factors.copy(),
            "Total Delta": round_dict_values(total_delta.copy()),
            "Total MMR": round_dict_values(last_adjusted_mmr.copy()),
            "Inflation Factor": round(inflation_factor[0], 2)
        })

    return table

