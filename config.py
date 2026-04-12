# Google Sheets and authentication
import os
ROOT = os.path.dirname(os.path.abspath(__file__))
SPREADSHEET_ID = "1wL1uCTaW9OJd3kfllbMMrUJileGvQcnE6t6dtaR_9So"

# --- Rocket League ---
# DB Sheets
RL_SHEETS = ["RL_Soccar", "RL_Gridiron", "RL_Hoops", "RL_Dropshot"]
# DB columns
RL_DATE_COL = "Date"
RL_MATCH_COL = "Match ID"
RL_BLUE_TEAM_COLS = ["Blue_1", "Blue_2", "Blue_3", "Blue_4"]
RL_ORANGE_TEAM_COLS = ["Orange_1", "Orange_2", "Orange_3", "Orange_4"]
RL_BLUE_SCORE_COL = "Goal_Blue"
RL_ORANGE_SCORE_COL = "Goal_Orange"
RL_OVERTIME_COL = "Overtime"
# Hyperparameters
RL_BASE_MMR = 1000
RL_GAMMA = 800
RL_K_FACTOR = 0.85
RL_BASE_MMR_DELTA = 25
RL_GOAL_DIFFERENCE_FACTOR = {"RL_Soccar": 6, "RL_Gridiron": 70, "RL_Hoops": 6, "RL_Dropshot": 3}
RL_BASE_UNCERTAINTY = 3.0
RL_UNCERTAINTY_DECAY = {"RL_Soccar": 0.1, "RL_Gridiron": 0.25, "RL_Hoops": 0.25, "RL_Dropshot": 0.25} # Per match
RL_UNCERTAINTY_INCREASE = 0.025 # Per day of inactivity
RL_MMR_DECAY_FACTOR_PER_DAY = 0.006
RL_MMR_RECLAIM = 30
RL_MAX_DECAY = 800
RL_ENGINE_LOG_FILE = os.path.join(ROOT, "logs", "rl_engine_handlers.log")
# Players
RL_DEACTIVATED_PLAYERS = []
RL_HIDDEN_PLAYERS = ["Gio", "Andre"]  # Players whose MMR is hidden from the leaderboard   

# --- Mario Kart ---
# DB Sheets
MK_SHEET = "MarioKart"
# DB columns
MK_DATE_COL = "Date"
MK_MATCH_COL = "Match ID"
MK_POSITION_COLS = ["1st", "2nd", "3rd", "4th", "5th", "6th", "7th", "8th"]
# Hyperparameters
MK_BASE_MMR = 1000
MK_GAMMA = 800          # ELO sensitivity for pairwise matchups
MK_BASE_MMR_DELTA = 25  # Max delta per pairwise matchup
MK_BASE_UNCERTAINTY = 3.0
MK_UNCERTAINTY_DECAY = 0.15   # Per race
MK_UNCERTAINTY_INCREASE = 0.025  # Per day of inactivity
MK_MMR_DECAY_FACTOR_PER_DAY = 0.006
MK_MMR_RECLAIM = 30
MK_MAX_DECAY = 800
MK_ENGINE_LOG_FILE = os.path.join(ROOT, "logs", "mk_engine_handlers.log")

# --- FIFA ---
# DB Sheets
FIFA_SHEET = "FIFA"
# DB columns
FIFA_DATE_COL = "Date"
FIFA_MATCH_COL = "Match ID"
FIFA_HOME_PLAYER_COL = "Home Player"
FIFA_AWAY_PLAYER_COL = "Away Player"
FIFA_HOME_SCORE_COL = "Home Score"
FIFA_AWAY_SCORE_COL = "Away Score"
FIFA_HOME_PENALTIES_SCORE_COL = "Home Penalties Score"
FIFA_AWAY_PENALTIES_SCORE_COL = "Away Penalties Score"
FIFA_HOME_STARS_COL = "Home Stars"
FIFA_AWAY_STARS_COL = "Away Stars"
# Hyperparameters
FIFA_BASE_MMR = 1000
FIFA_BASE_MMR_DELTA = 25
FIFA_BASE_UNCERTAINTY = 3.0
FIFA_GAMMA = 1600
FIFA_UNCERTAINTY_INCREASE = 0.025
FIFA_UNCERTAINTY_DECAY = 0.1
FIFA_GOAL_DIFFERENCE_FACTOR = 6
FIFA_STAR_RATING_FACTOR = 100 # Extra MMR difference per star difference
FIFA_MMR_DECAY_FACTOR_PER_DAY = 0.006
FIFA_MMR_RECLAIM = 30
FIFA_MAX_DECAY = 800
FIFA_ENGINE_LOG_FILE = os.path.join(ROOT, "logs", "fifa_engine_handlers.log")
