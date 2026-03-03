import os


ROOT = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(ROOT, "partite_rocket.xlsx")

SHEETS = ["Carlcio", "NFL", "Canestro", "Dropshot"]

PLAYERS = ["Ema", "Fede", "Cris", "Marco", "Peppe B", "Peppe N", "Gio", "Andre", "Michi"]

PLAYER_COLORS = {
    "Marco": "#1f77b4",     # Blu
    "Ema": "#ff7f0e",    # Arancione
    "Fede": "#2ca02c",    # Verde
    "Peppe B": "#d62728",   # Rosso
    "Cris": "#9467bd", # Viola
    "Peppe N": "#8c564b", # Marrone
    "Gio": "#e377c2",     # Rosa
    "Andre": "#7f7f7f",   # Grigio
    "Michi": "#bcbd22",   # Verde-Giallo
}

DATE_COL = "Data"
MATCH_COL = "Numero Partita"
BLUE_TEAM_COLS = ["Blue_1", "Blue_2", "Blue_3", "Blue_4"]
ORANGE_TEAM_COLS = ["Orange_1", "Orange_2", "Orange_3", "Orange_4"]
BLUE_SCORE_COL = "Gol_Blue"
ORANGE_SCORE_COL = "Gol_Orange"
OVERTIME_COL = "Supplementari"

BASE_MMR = 1000
GAMMA = 400
K_FACTOR = 0.85
BASE_MMR_DELTA = 50
GOAL_DIFFERENCE_FACTOR = {"Carlcio": 7, "NFL": 70, "Canestro": 7, "Dropshot": 3}
BASE_UNCERTAINTY = 3.0
UNCERTAINTY_DECAY = {"Carlcio": 0.1, "NFL": 0.25, "Canestro": 0.25, "Dropshot": 0.25} # Per match
UNCERTAINTY_INCREASE = 0.025 # Per giorno senza giocare
MMR_DECAY_PER_DAY = 0.005 # Percentuale punteggio da sottrarre al giocatore per ogni giorno senza giocare dopo aver raggiunto l'incertezza massima