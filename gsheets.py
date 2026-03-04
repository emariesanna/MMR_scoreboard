import gspread
import pandas as pd
import streamlit as st
from google.oauth2.service_account import Credentials

import os
from config import SPREADSHEET_ID, DATE_COL, OVERTIME_COL, ROOT

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

_CREDENTIALS_FILE = os.path.join(ROOT, "credentials.json")


def _get_client() -> gspread.Client:
    # On Streamlit Cloud: load credentials from st.secrets
    # Locally: fall back to credentials.json if secrets are not configured
    if "gcp_service_account" in st.secrets:
        creds = Credentials.from_service_account_info(
            dict(st.secrets["gcp_service_account"]), scopes=SCOPES
        )
    else:
        creds = Credentials.from_service_account_file(_CREDENTIALS_FILE, scopes=SCOPES)
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
    # Parse date column
    if DATE_COL in df.columns:
        df[DATE_COL] = pd.to_datetime(df[DATE_COL], dayfirst=True)
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
