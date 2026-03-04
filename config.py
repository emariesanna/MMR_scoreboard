import os


ROOT = os.path.dirname(os.path.abspath(__file__))
# DB = os.path.join(ROOT, "partite_rocket.xlsx")  # legacy: local Excel file
SPREADSHEET_ID = "1wL1uCTaW9OJd3kfllbMMrUJileGvQcnE6t6dtaR_9So"

SHEETS = ["Carlcio", "NFL", "Canestro", "Dropshot"]

PLAYERS = ["Ema", "Fede", "Cris", "Marco", "Peppe B", "Peppe N", "Gio", "Andre", "Michi"]

PLAYER_COLORS = {
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

DATE_COL = "Date"
MATCH_COL = "Match ID"
BLUE_TEAM_COLS = ["Blue_1", "Blue_2", "Blue_3", "Blue_4"]
ORANGE_TEAM_COLS = ["Orange_1", "Orange_2", "Orange_3", "Orange_4"]
BLUE_SCORE_COL = "Goal_Blue"
ORANGE_SCORE_COL = "Goal_Orange"
OVERTIME_COL = "Overtime"

BASE_MMR = 1000
GAMMA = 400
K_FACTOR = 0.85
BASE_MMR_DELTA = 50
GOAL_DIFFERENCE_FACTOR = {"Carlcio": 7, "NFL": 70, "Canestro": 7, "Dropshot": 3}
BASE_UNCERTAINTY = 3.0
UNCERTAINTY_DECAY = {"Carlcio": 0.1, "NFL": 0.25, "Canestro": 0.25, "Dropshot": 0.25} # Per match
UNCERTAINTY_INCREASE = 0.025 # Per day of inactivity
MMR_DECAY_PER_DAY = 0.005 # Percentage of score to subtract from the player for each day without playing after reaching maximum uncertainty