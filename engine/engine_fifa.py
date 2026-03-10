from collections import defaultdict

import pandas as pd

from config import (
    FIFA_DATE_COL, FIFA_MATCH_COL, FIFA_HOME_PLAYER_COL, FIFA_AWAY_PLAYER_COL, FIFA_HOME_SCORE_COL,
    FIFA_AWAY_SCORE_COL, FIFA_HOME_PENALTIES_SCORE_COL, FIFA_AWAY_PENALTIES_SCORE_COL, FIFA_HOME_STARS_COL,
    FIFA_AWAY_STARS_COL,

    FIFA_BASE_MMR, FIFA_BASE_MMR_DELTA, FIFA_BASE_UNCERTAINTY, FIFA_GAMMA, FIFA_MMR_DECAY_PER_DAY,
    FIFA_UNCERTAINTY_INCREASE, FIFA_UNCERTAINTY_DECAY, FIFA_GOAL_DIFFERENCE_FACTOR, FIFA_STAR_RATING_FACTOR,
)
from gsheets import read_sheet_df
from engine.handlers import (
    InactivityHandler,
    UncertaintyHandler,
    InflationHandler,
    FifaTeamMatchHandler,
    GoalDifferenceHandler,
)
from utils import format_date, round_dict_values


def get_fifa_table(sheet_name: str) -> list:
    # table structure:
    # {
    #   "Date": str,                            # Match date (es. "05-Mar-24")
    #   "Match": int,                           # Sequential match number
    #   "Home Player": str,                     # Name of the home player
    #   "Away Player": str,                     # Name of the away player
    #   "Home Score": int,                      # Goals scored by the home team
    #   "Away Score": int,                      # Goals scored by the away team
    #   "Home Penalties Score": int,            # Goals score by the home team in penalties phase (if applicable)
    #   "Away Penalties Score": int,            # Goals score by the away team in penalties phase (if applicable)
    #   "Home team rating": float,              # Star rating of the home team (1.0 to 5.0)
    #   "Away team rating": float,              # Star rating of the away team (1.0 to 5.0)
    #   "Home Win Prob.": float,                # Expected probability of home team winning
    #   "Away Win Prob.": float,                # Expected probability of away team winning
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
    last_mmr = defaultdict(lambda: FIFA_BASE_MMR)
    uncertainty_factors = defaultdict(lambda: FIFA_BASE_UNCERTAINTY)
    last_date_mmr = defaultdict(lambda: FIFA_BASE_MMR)

    # Initialize handlers
    inactivity = InactivityHandler(active_players, last_mmr, uncertainty_factors, last_date_mmr, 
                                   FIFA_UNCERTAINTY_INCREASE, FIFA_MMR_DECAY_PER_DAY, FIFA_BASE_UNCERTAINTY)
    uncertainty = UncertaintyHandler(last_mmr, uncertainty_factors, FIFA_UNCERTAINTY_DECAY)
    inflation = InflationHandler(active_players, last_mmr)
    team_match = FifaTeamMatchHandler(last_mmr, last_date_mmr, FIFA_BASE_MMR_DELTA, FIFA_GAMMA, FIFA_STAR_RATING_FACTOR)
    goal_diff = GoalDifferenceHandler(last_mmr, FIFA_GOAL_DIFFERENCE_FACTOR)

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

        # Process inactivity effects (uncertainty increase and MMR decay)
        decay_delta = inactivity.process_date_change(date_val)
        
        # Calculate decay inflation (separate from uncertainty inflation)
        decay_inflation_delta = inflation.apply_inflation_correction(sum(decay_delta.values()))

        # Calculate MMR difference
        mmr_diff = team_match.calculate_mmr_diff(home_player, away_player, home_stars, away_stars)
        # Calculate win probabilities
        home_win_prob, away_win_prob = team_match.calculate_win_probability(mmr_diff)

        # Apply match outcome
        if home_score != away_score:
            home_won = home_score > away_score
            penalties = False
        elif home_penalties_score != away_penalties_score: 
            home_won = home_penalties_score > away_penalties_score
            penalties = True
        else:
            home_won = 0.5  # Draw
            penalties = False
        match_delta = team_match.apply_match_outcome(home_player, away_player, home_won, home_win_prob, penalties)

        # Apply goal difference bonus/penalty
        goal_difference_delta = goal_diff.apply_goal_difference([home_player], [away_player], home_score, away_score, 
                                                                match_delta, penalties)

        # Apply uncertainty amplification and reduce uncertainty
        pre_match_uncertainty = uncertainty_factors.copy()
        combined_deltas = {p: match_delta.get(p, 0) + goal_difference_delta.get(p, 0) for p in [home_player, away_player]}
        uncertainty_delta = uncertainty.apply_uncertainty_amplification([home_player, away_player], combined_deltas)

        # Update active players
        active_players.update([home_player, away_player])

        # Calculate uncertainty inflation (separate from decay inflation)
        uncertainty_inflation_delta = inflation.apply_inflation_correction(sum(uncertainty_delta.values()))

        # Calculate total delta and total MMR
        total_delta = {}
        total_mmr = {}
        for p in active_players:
            total_delta[p] = (
                match_delta.get(p, 0)
                + goal_difference_delta.get(p, 0)
                + uncertainty_delta.get(p, 0)
                + decay_delta.get(p, 0)
                + decay_inflation_delta.get(p, 0)
                + uncertainty_inflation_delta.get(p, 0)
            )
            total_mmr[p] = last_mmr[p]

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
            "Home Win Prob.": home_win_prob,              
            "Away Win Prob.": away_win_prob,              
            "Uncertainty Factors": pre_match_uncertainty.copy(),  
            "Match Delta": round_dict_values(match_delta),  
            "Goal Difference Delta": round_dict_values(goal_difference_delta),
            "Uncertainty Delta": round_dict_values(uncertainty_delta),
            "Decay Delta": round_dict_values(decay_delta),
            "Decay Inflation Delta": round_dict_values(decay_inflation_delta),
            "Uncertainty Inflation Delta": round_dict_values(uncertainty_inflation_delta),
            "Total Delta": round_dict_values(total_delta),
            "Total MMR": round_dict_values(total_mmr),
        })

    return table