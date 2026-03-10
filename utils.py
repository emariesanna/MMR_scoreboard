"""Utility functions for MMR calculation engines."""
import pandas as pd
from datetime import date
from typing import Any


def format_date(date_val) -> str:
    """
    Format a date value to standard string format (DD-Mon-YY).
    
    Args:
        date_val: Date value (pd.Timestamp, datetime, or string)
    
    Returns:
        Formatted date string (e.g., "15-Jan-24")
    """
    if hasattr(date_val, "strftime"):
        return date_val.strftime("%d-%b-%y")
    return str(date_val)


def safe_bool(value, default: bool = False) -> bool:
    """
    Safely convert a value to boolean with robust handling.
    
    Args:
        value: Value to convert (can be bool, int, float, str, or NaN)
        default: Default value if conversion fails
    
    Returns:
        Boolean value or default
    """
    if pd.isna(value):
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        v = value.strip().lower()
        if v in {"true", "1", "yes", "y"}:
            return True
        if v in {"false", "0", "no", "n", ""}:
            return False
    return default


def safe_str(value, default: str = "") -> str:
    """
    Safely convert a value to string with NaN handling.
    
    Args:
        value: Value to convert
        default: Default string if value is NaN
    
    Returns:
        String value or default
    """
    if pd.isna(value):
        return default
    return str(value).strip()


def get_today() -> date:
    """Get today's date."""
    return date.today()


def round_dict_values(d: dict[str, float]) -> dict[str, int]:
    """
    Round all numeric values in a dict to integers.
    
    Args:
        d: Dictionary with string keys and float values
    
    Returns:
        New dictionary with rounded integer values
    """
    return {k: round(v) for k, v in d.items()}