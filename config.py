import os


ROOT = os.path.dirname(os.path.abspath(__file__))
SPREADSHEET_ID = "1wL1uCTaW9OJd3kfllbMMrUJileGvQcnE6t6dtaR_9So"

SHEETS_RL = ["RL_Carlcio", "RL_NFL", "RL_Canestro", "RL_Dropshot"]
SHEETS_MK = ["MarioKart"]

RL_PLAYERS = ["Ema", "Fede", "Cris", "Marco", "Peppe B", "Peppe N", "Gio", "Andre", "Michi"]
MK_PLAYERS = ["Ema", "Fede", "Marco", "Peppe N", "Michi", "Mari", "Giuli", "Eli", "Fra"]

RL_PLAYER_COLORS = {
    "Marco": "#1f77b4",     # Blue
    "Ema": "#ff7f0e",       # Orange
    "Fede": "#2ca02c",      # Green
    "Peppe B": "#d62728",   # Red
    "Cris": "#9467bd",      # Purple
    "Peppe N": "#8c564b",   # Brown
    "Gio": "#e377c2",       # Pink
    "Michi": "#bcbd22",     # Yellow
    "Andre": "#17becf",     # Cyan
}

MK_PLAYER_COLORS = {
    "Marco": "#1f77b4",     # Blue
    "Ema": "#ff7f0e",       # Orange
    "Fede": "#2ca02c",      # Green
    "Peppe N": "#d62728",   # Red
    "Michi": "#bcbd22",     # Yellow
    "Mari": "#8c564b",      # Brown
    "Giuli": "#e377c2",       # Pink
    "Eli": "#9467bd",      # Purple
    "Fra": "#17becf",     # Cyan
}

# --- Rocket League ---
DATE_COL = "Date"
MATCH_COL = "Match ID"
BLUE_TEAM_COLS = ["Blue_1", "Blue_2", "Blue_3", "Blue_4"]
ORANGE_TEAM_COLS = ["Orange_1", "Orange_2", "Orange_3", "Orange_4"]
BLUE_SCORE_COL = "Goal_Blue"
ORANGE_SCORE_COL = "Goal_Orange"
OVERTIME_COL = "Overtime"
BASE_MMR = 1000
GAMMA = 800
K_FACTOR = 0.85
BASE_MMR_DELTA = 25
GOAL_DIFFERENCE_FACTOR = {"RL_Carlcio": 7, "RL_NFL": 70, "RL_Canestro": 7, "RL_Dropshot": 3}
BASE_UNCERTAINTY = 3.0
UNCERTAINTY_DECAY = {"RL_Carlcio": 0.1, "RL_NFL": 0.25, "RL_Canestro": 0.25, "RL_Dropshot": 0.25} # Per match
UNCERTAINTY_INCREASE = 0.025 # Per day of inactivity
MMR_DECAY_PER_DAY = 0.005 # Percentage of score to subtract from the player for each day without playing after reaching maximum uncertainty

# --- Mario Kart ---
MK_DATE_COL = "Date"
MK_MATCH_COL = "Match ID"
MK_POSITION_COLS = ["1st", "2nd", "3rd", "4th", "5th", "6th", "7th", "8th"]
MK_BASE_MMR = 1000
MK_GAMMA = 400          # ELO sensitivity for pairwise matchups
MK_BASE_MMR_DELTA = 32  # Max delta per pairwise matchup
MK_BASE_UNCERTAINTY = 3.0
MK_UNCERTAINTY_DECAY = 0.15   # Per race
MK_UNCERTAINTY_INCREASE = 0.025  # Per day of inactivity
MK_MMR_DECAY_PER_DAY = 0.005