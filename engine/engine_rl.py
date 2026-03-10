import pandas as pd
from collections import defaultdict
from engine.handlers.team_match_handler import RLTeamMatchHandler
from gsheets import read_sheet_df
from engine.handlers import (
    InactivityHandler, UncertaintyHandler, EqualInflationHandler, GoalDifferenceHandler
)
from utils import format_date, round_dict_values
from config import (
    RL_DATE_COL, RL_MATCH_COL, RL_BLUE_TEAM_COLS, RL_ORANGE_TEAM_COLS, RL_BLUE_SCORE_COL, 
    RL_ORANGE_SCORE_COL, RL_OVERTIME_COL,

    RL_BASE_MMR, RL_GAMMA, RL_K_FACTOR, RL_BASE_MMR_DELTA, RL_GOAL_DIFFERENCE_FACTOR, 
    RL_BASE_UNCERTAINTY, RL_UNCERTAINTY_DECAY, RL_UNCERTAINTY_INCREASE, RL_MMR_DECAY_PER_DAY 
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
    #   "Match Delta": {str: float},            # MMR delta from match outcome for each player in the game
    #   "Goal Difference Delta": {str: float},  # MMR delta from goal difference for each player in the game
    #   "Uncertainty Delta": {str: float},      # MMR delta from uncertainty factors for each player in the game
    #   "Decay Delta": {str: float},            # MMR delta from decay for each active player
    #   "Inflation Delta": {str: float},        # MMR delta from inflation for each active player
    #   "Total Delta": {str: float},            # Total MMR delta for each active player
    #   "Total MMR": {str: float}               # Total updated MMR for each player
    # }
    table = []
    
    # Initialize shared state
    active_players = set()
    last_mmr = defaultdict(lambda: RL_BASE_MMR)
    uncertainty_factors = defaultdict(lambda: RL_BASE_UNCERTAINTY)
    last_date_mmr = defaultdict(lambda: RL_BASE_MMR)
    
    # Initialize handlers
    inactivity = InactivityHandler(active_players, last_mmr, uncertainty_factors, last_date_mmr, 
                                   RL_UNCERTAINTY_INCREASE, RL_MMR_DECAY_PER_DAY, RL_BASE_UNCERTAINTY)
    uncertainty = UncertaintyHandler(last_mmr, uncertainty_factors, RL_UNCERTAINTY_DECAY[sheet_name])
    inflation = EqualInflationHandler(active_players, last_mmr)
    team_match = RLTeamMatchHandler(last_mmr, last_date_mmr, RL_BASE_MMR_DELTA, RL_GAMMA, RL_K_FACTOR)
    goal_diff = GoalDifferenceHandler(last_mmr, RL_GOAL_DIFFERENCE_FACTOR[sheet_name])

    for _, rows in read_sheet_df(sheet_name).iterrows():
        # Extract match data
        date_val = pd.to_datetime(rows[RL_DATE_COL])
        date_str = format_date(date_val)
        match_num = int(rows[RL_MATCH_COL])
        blue_team = [p for p in rows[RL_BLUE_TEAM_COLS] if pd.notna(p)]
        orange_team = [p for p in rows[RL_ORANGE_TEAM_COLS] if pd.notna(p)]
        blue_score = rows[RL_BLUE_SCORE_COL]
        orange_score = rows[RL_ORANGE_SCORE_COL]
        overtime = rows[RL_OVERTIME_COL]

        # Process inactivity effects (uncertainty increase and MMR decay)
        decay_delta = inactivity.process_date_change(date_val)
        
        # Process date change for uncertainty (snapshot at beginning of day)
        uncertainty.process_date_change(date_val)
        
        # Calculate decay inflation (separate from uncertainty inflation)
        decay_inflation_delta = inflation.apply_inflation_correction(sum(decay_delta.values()))

        # Calculate MMR difference
        mmr_difference = team_match.calculate_mmr_diff(blue_team, orange_team)

        # Calculate win probabilities
        blue_win_prob, orange_win_prob = team_match.calculate_win_probability(mmr_difference)

        # Apply match outcome (with overtime consideration)
        blue_win = blue_score > orange_score
        match_delta = team_match.apply_match_outcome(blue_team, orange_team, blue_win, blue_win_prob, overtime)
        
        # Apply goal difference bonus/penalty
        goal_difference_delta = goal_diff.apply_goal_difference(
            blue_team, orange_team, blue_score, orange_score, match_delta, overtime
        )

        # Apply uncertainty amplification and reduce uncertainty
        pre_match_uncertainty = uncertainty_factors.copy()
        combined_deltas = {p: match_delta.get(p, 0) + goal_difference_delta.get(p, 0) 
                          for p in blue_team + orange_team}
        uncertainty_delta = uncertainty.apply_uncertainty_amplification(
            blue_team + orange_team, combined_deltas
        )

        # Update active players
        active_players.update(blue_team + orange_team)

        # Calculate uncertainty inflation (separate from decay inflation)
        uncertainty_inflation_delta = inflation.apply_inflation_correction(sum(uncertainty_delta.values()))

        # Calculate total delta and total MMR
        total_delta = {}
        total_mmr = {}
        for p in active_players:
            total_delta[p] = (match_delta.get(p, 0) + goal_difference_delta.get(p, 0) + 
                            uncertainty_delta.get(p, 0) + decay_delta.get(p, 0) +
                            decay_inflation_delta.get(p, 0) + uncertainty_inflation_delta.get(p, 0))
            total_mmr[p] = last_mmr[p]

        # Append match row to table (round all deltas and MMR to integers)
        table.append({
            "Date": date_str,
            "Match": match_num,
            "Blue Team": blue_team,
            "Orange Team": orange_team,
            "Blue Score": blue_score,
            "Orange Score": orange_score,
            "Overtime": overtime,
            "Blue Win Prob.": round(blue_win_prob, 2),
            "Orange Win Prob.": round(orange_win_prob, 2),
            "Uncertainty Factors": pre_match_uncertainty.copy(),
            "Match Delta": round_dict_values(match_delta),
            "Goal Difference Delta": round_dict_values(goal_difference_delta),
            "Uncertainty Delta": round_dict_values(uncertainty_delta),
            "Decay Delta": round_dict_values(decay_delta),
            "Decay Inflation Delta": round_dict_values(decay_inflation_delta),
            "Uncertainty Inflation Delta": round_dict_values(uncertainty_inflation_delta),
            "Total Delta": round_dict_values(total_delta),
            "Total MMR": round_dict_values(total_mmr)
        })

    return table

