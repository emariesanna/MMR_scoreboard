import pandas as pd
import json, os
from config import ROOT
from gsheets import read_sheet_df

from config import BASE_MMR, BASE_MMR_DELTA, BASE_UNCERTAINTY, BLUE_SCORE_COL, BLUE_TEAM_COLS, DATE_COL, GAMMA, GOAL_DIFFERENCE_FACTOR, K_FACTOR, MMR_DECAY_PER_DAY, ORANGE_SCORE_COL, ORANGE_TEAM_COLS, RL_PLAYERS, OVERTIME_COL, UNCERTAINTY_DECAY, UNCERTAINTY_INCREASE

def get_table(sheet_name):
    # table structure:
    # {
    #   "Date": str,                            # Match date (es. "05-Mar-24")
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
    
    active_players = set() # Set to keep track of active players (those who have played at least one match)
    last_mmr = {p: BASE_MMR for p in RL_PLAYERS}
    last_date = None
    last_date_mmr = {p: BASE_MMR for p in RL_PLAYERS}
    uncertainty_factors = {}

    db = read_sheet_df(sheet_name)

    for _, rows in db.iterrows():
        match_delta = {}
        goal_difference_delta = {}
        uncertainty_delta = {}
        decay_delta = {}
        inflation_delta = {}
        total_delta = {}
        total_mmr = {}

        date_val = rows[DATE_COL]
        date_str = date_val.strftime("%d-%b-%y")
        blue_team = [p for p in rows[BLUE_TEAM_COLS] if pd.notna(p)]
        orange_team = [p for p in rows[ORANGE_TEAM_COLS] if pd.notna(p)]
        blue_score = rows[BLUE_SCORE_COL]
        orange_score = rows[ORANGE_SCORE_COL]
        overtime = rows[OVERTIME_COL]

        # Win probability calculation
        if last_date is not None and date_val != last_date:
            last_date_mmr = last_mmr.copy()
        orange_size = len(orange_team)
        blue_size = len(blue_team)
        orange_MMR = sum(last_date_mmr[p] for p in orange_team)*orange_size**(K_FACTOR-1)
        blue_MMR = sum(last_date_mmr[p] for p in blue_team)*blue_size**(K_FACTOR-1)
        mean_team_size = (blue_size + orange_size) / 2
        blue_win_prob = 1 / (1 + 10 ** ((orange_MMR - blue_MMR)/mean_team_size / GAMMA))
        orange_win_prob = 1 - blue_win_prob

        # Match delta calculation
        blue_win = 1 if blue_score > orange_score else 0
        base_blue_match_delta = BASE_MMR_DELTA * (blue_win - blue_win_prob)
        blue_match_delta = base_blue_match_delta * orange_size / blue_size
        orange_match_delta = -base_blue_match_delta * blue_size / orange_size
        for p in blue_team:
            match_delta[p] = blue_match_delta
            last_mmr[p] += blue_match_delta 
        for p in orange_team:
            match_delta[p] = orange_match_delta
            last_mmr[p] += orange_match_delta

        # Goal difference delta calculation
        goal_diff_factor = abs(blue_score - orange_score) / GOAL_DIFFERENCE_FACTOR[sheet_name] if not overtime else 0
        blue_goal_diff_delta = blue_match_delta * goal_diff_factor
        orange_goal_diff_delta = orange_match_delta * goal_diff_factor
        for p in blue_team:
            goal_difference_delta[p] = blue_goal_diff_delta
            last_mmr[p] += blue_goal_diff_delta
        for p in orange_team:
            goal_difference_delta[p] = orange_goal_diff_delta
            last_mmr[p] += orange_goal_diff_delta

        # Uncertainty increase due to time passed and decay delta calculation
        if last_date is None:
            uncertainty_factors = {p: BASE_UNCERTAINTY for p in RL_PLAYERS}
            last_date = date_val
        else:
            if last_date != date_val:
                uncertainty_diff = UNCERTAINTY_INCREASE * (date_val - last_date).days if last_date else 0
                for p in active_players:
                    if uncertainty_factors[p] + uncertainty_diff < BASE_UNCERTAINTY:
                        uncertainty_factors[p] = round(uncertainty_factors[p] + uncertainty_diff, 6)
                    else:
                        decay_delta[p] = -(uncertainty_factors[p] + uncertainty_diff - BASE_UNCERTAINTY) / UNCERTAINTY_INCREASE * MMR_DECAY_PER_DAY * last_date_mmr[p]
                        last_mmr[p] += decay_delta[p]
                        uncertainty_factors[p] = BASE_UNCERTAINTY
                last_date = date_val
        
        # Uncertainty delta calculation and uncertainty decrease due to match participation
        pre_match_uncertainty = uncertainty_factors.copy()
        for p in blue_team + orange_team:
            uncertainty_delta[p] = (match_delta[p] + goal_difference_delta[p]) * (uncertainty_factors[p] - 1)
            last_mmr[p] += uncertainty_delta[p]
            uncertainty_factors[p] = round(max(1.0, uncertainty_factors[p] - UNCERTAINTY_DECAY[sheet_name]), 6)

        # Active players update
        active_players.update(blue_team + orange_team)

        # Inflation delta calculation
        inflation = sum(uncertainty_delta.values()) + sum(decay_delta.values())
        for p in active_players:
            inflation_delta[p] = -inflation * (last_mmr[p] / sum(last_mmr[ap] for ap in active_players))
            last_mmr[p] += inflation_delta[p]

        # Total delta and total MMR calculation
        for p in active_players:
            total_delta[p] = match_delta.get(p, 0) + goal_difference_delta.get(p, 0) + uncertainty_delta.get(p, 0) + decay_delta.get(p, 0) + inflation_delta.get(p, 0)
            total_mmr[p] = last_mmr[p]

        # Table row insertion
        table.append({
            "Date": date_str,
            "Blue Team": blue_team,
            "Orange Team": orange_team,
            "Blue Score": blue_score,
            "Orange Score": orange_score,
            "Overtime": overtime,
            "Blue Win Prob.": round(blue_win_prob, 2),
            "Orange Win Prob.": round(orange_win_prob, 2),
            "Uncertainty Factors": pre_match_uncertainty.copy(),
            "Match Delta": match_delta.copy(),
            "Goal Difference Delta": goal_difference_delta.copy(),
            "Uncertainty Delta": uncertainty_delta.copy(),
            "Decay Delta": decay_delta.copy(),
            "Inflation Delta": inflation_delta.copy(),
            "Total Delta": total_delta.copy(),
            "Total MMR": total_mmr.copy()
        })

    # Logging the table to a JSON file for debugging purposes
    log_path = os.path.join(ROOT, f"Log_{sheet_name}.json")
    with open(log_path, "w", encoding="utf-8") as f:
        json.dump(table, f, indent=2, ensure_ascii=False, default=str)

    return table

