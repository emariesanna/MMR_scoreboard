import gspread
import pandas as pd
import streamlit as st
from google.oauth2.service_account import Credentials

import os
from config import SPREADSHEET_ID, DATE_COL, OVERTIME_COL, MK_DATE_COL, ROOT

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

_CREDENTIALS_FILE = os.path.join(ROOT, "credentials.json")


def _get_client() -> gspread.Client:
    # Prefer credentials.json if it exists (local development)
    # Fall back to st.secrets (Streamlit Cloud deployment)
    if os.path.exists(_CREDENTIALS_FILE):
        creds = Credentials.from_service_account_file(_CREDENTIALS_FILE, scopes=SCOPES)
    elif "gcp_service_account" in st.secrets:
        info = dict(st.secrets["gcp_service_account"])
        if "private_key" in info:
            key = info["private_key"]
            key = key.replace("\\n", "\n").replace("\r\n", "\n").replace("\r", "\n")
            info["private_key"] = key.strip()
        creds = Credentials.from_service_account_info(info, scopes=SCOPES)
    else:
        raise FileNotFoundError("No credentials found: provide credentials.json or configure st.secrets.")
    return gspread.authorize(creds)


@st.cache_data(ttl=60)
def read_sheet_df(sheet_name: str) -> pd.DataFrame:
    """Reads a Google Sheets worksheet and returns a pandas DataFrame.
    The result is cached for 60 seconds to reduce API calls."""
    client = _get_client()
    sh = client.open_by_key(SPREADSHEET_ID)
    ws = sh.worksheet(sheet_name)
    data = ws.get_all_records(default_blank=None)
    if not data:
        return pd.DataFrame()
    df = pd.DataFrame(data)
    # Parse date column for RL sheets
    if DATE_COL in df.columns:
        df[DATE_COL] = pd.to_datetime(df[DATE_COL], format="ISO8601")
    # Parse date column for MK sheets
    elif MK_DATE_COL in df.columns:
        df[MK_DATE_COL] = pd.to_datetime(df[MK_DATE_COL], format="ISO8601")
    # Parse overtime boolean
    if OVERTIME_COL in df.columns:
        df[OVERTIME_COL] = df[OVERTIME_COL].map(
            lambda v: True if v in (True, 1, "TRUE", "True", "true", "1") else False
        )
    return df


def append_match(sheet_name: str, row_values: list) -> None:
    """Appends a row of data to a Google Sheets worksheet."""
    client = _get_client()
    sh = client.open_by_key(SPREADSHEET_ID)
    ws = sh.worksheet(sheet_name)
    ws.append_row(row_values, value_input_option="RAW")


def append_mk_race(sheet_name: str, row_values: list) -> None:
    """Appends a Mario Kart race row to a Google Sheets worksheet."""
    client = _get_client()
    sh = client.open_by_key(SPREADSHEET_ID)
    ws = sh.worksheet(sheet_name)
    ws.append_row(row_values, value_input_option="RAW")


_PLAYERS_SHEET = "Players"


@st.cache_data(ttl=60)
def read_players_df() -> pd.DataFrame:
    """Reads the Players sheet (Color Name, Color Code, game columns) and returns a DataFrame."""
    client = _get_client()
    sh = client.open_by_key(SPREADSHEET_ID)
    ws = sh.worksheet(_PLAYERS_SHEET)
    data = ws.get_all_records(default_blank=None)
    if not data:
        return pd.DataFrame()
    return pd.DataFrame(data)


def get_game_players(game_col: str):
    """Returns (players: list[str], color_map: dict[str, str]) from the Players sheet for the given game column."""
    df = read_players_df()
    if df.empty or game_col not in df.columns:
        return [], {}
    players = []
    color_map = {}
    for _, row in df.iterrows():
        name = str(row.get(game_col) or "").strip()
        code = str(row.get("Color Code") or "").strip()
        if name:
            players.append(name)
            if code:
                color_map[name] = f"#{code}" if not code.startswith("#") else code
    return players, color_map


def append_player(name: str, game_cols: list, color_code: str = "") -> None:
    """Appends a new player row to the Players sheet."""
    client = _get_client()
    sh = client.open_by_key(SPREADSHEET_ID)
    ws = sh.worksheet(_PLAYERS_SHEET)
    headers = ws.row_values(1)
    row = [""] * len(headers)
    for i, h in enumerate(headers):
        if h == "Color Code":
            row[i] = color_code.lstrip("#")
        elif h in game_cols:
            row[i] = name
    ws.append_row(row, value_input_option="RAW")
