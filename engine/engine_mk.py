import logging
import os
from collections import defaultdict

import pandas as pd

from config import (
    MK_DATE_COL, MK_MATCH_COL, MK_POSITION_COLS, MK_BASE_MMR, MK_GAMMA, MK_BASE_MMR_DELTA,
    MK_BASE_UNCERTAINTY, MK_UNCERTAINTY_DECAY, MK_UNCERTAINTY_INCREASE, MK_MMR_DECAY_FACTOR_PER_DAY,
    MK_MMR_RECLAIM, MK_MAX_DECAY, MK_ENGINE_LOG_FILE,
)
from gsheets import read_sheet_df
from engine.handlers import UncertaintyHandler, CappedDecayHandler, InflationHandler
from engine.handlers.free_for_all_match_handler import FreeForAllMatchHandler
from engine.handlers.inactivity_handler import InactivityHandler
from utils import format_date, round_dict_values, sum_dicts, sum_default_dicts


def _setup_mk_handler_logger() -> logging.Logger:
    logger = logging.getLogger("mk_engine_handlers")
    if logger.handlers:
        return logger

    os.makedirs(os.path.dirname(MK_ENGINE_LOG_FILE), exist_ok=True)

    logger.setLevel(logging.INFO)
    logger.propagate = False

    file_handler = logging.FileHandler(MK_ENGINE_LOG_FILE, mode="w", encoding="utf-8")
    formatter = logging.Formatter("%(asctime)s | %(levelname)s | %(message)s")
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    return logger


def get_mk_table(sheet_name: str) -> list:
    """
    Process Mario Kart races and calculate MMR changes.
    
    table entry structure:
    {
        "Date": str,
        "Race": int,
        "Players": [str],
        "Uncertainty Factors": {str: float},
        "Race Delta": {str: float},
        "Uncertainty Delta": {str: float},
        "Decay Delta": {str: float},
        "Decay Inflation Delta": {str: float},
        "Uncertainty Inflation Delta": {str: float},
        "Total Delta": {str: float},
        "Total MMR": {str: float}
    }
    """
    table = []
    
    # Initialize session state
    active_players = set()
    adjusted_mmrs = defaultdict(lambda: MK_BASE_MMR)
    raw_mmrs = defaultdict(lambda: MK_BASE_MMR)
    logger = _setup_mk_handler_logger()

    logger.info("=== MK engine start | sheet=%s ===", sheet_name)

    # Initialize handlers
    ffa_match = FreeForAllMatchHandler(MK_BASE_MMR_DELTA, MK_GAMMA, logger_name="mk_engine_handlers")
    inactivity = InactivityHandler(logger_name="mk_engine_handlers")
    uncertainty = UncertaintyHandler(MK_BASE_MMR_DELTA, MK_UNCERTAINTY_DECAY, MK_UNCERTAINTY_INCREASE, MK_BASE_UNCERTAINTY, logger_name="mk_engine_handlers")
    decay = CappedDecayHandler(MK_MMR_DECAY_FACTOR_PER_DAY, MK_MMR_RECLAIM, MK_MAX_DECAY, logger_name="mk_engine_handlers")
    inflation = InflationHandler(MK_BASE_MMR, logger_name="mk_engine_handlers")

    for _, row in read_sheet_df(sheet_name).iterrows():
        # Extract race data
        date_val = pd.to_datetime(row[MK_DATE_COL])
        date_str = format_date(date_val)
        race_num = int(row[MK_MATCH_COL])
        # Collect finishing order: columns 1st..8th, skip blanks
        players_ordered = [row[col] for col in MK_POSITION_COLS
                           if col in row.index and pd.notna(row[col]) and row[col] != ""]

        logger.info(
            "RACE_START | date=%s | race=%s | players=%s",
            date_str, race_num, players_ordered,
        )

        # Process match outcome
        ffa_match.process_match_outcome(date_val, players_ordered, raw_mmrs)
        
        # Process inactivity
        inactivity.process_inactivity(date_val, active_players)
        
        # Update active players
        active_players.update(players_ordered)

        # Process uncertainty
        uncertainty.process_uncertainty(
            ffa_match.get_match_deltas(),
            inactivity.get_inactivity_days())
        
        # Calculate total delta
        total_delta = sum_dicts([ffa_match.get_match_deltas(), uncertainty.get_uncertainty_deltas()])

        # Update raw MMRs
        raw_mmrs = sum_default_dicts([raw_mmrs, total_delta])

        # Process decay
        decay.process_decay(players_ordered, uncertainty.get_inactivity_days(), adjusted_mmrs)

        # Update adjusted MMRs with total delta and decay
        adjusted_mmrs = sum_default_dicts([adjusted_mmrs, total_delta, decay.get_decay_adjustment_deltas()])

        # Process inflation
        inflation.process_inflation(
            sum_dicts([uncertainty.get_uncertainty_deltas(), decay.get_decay_adjustment_deltas()]),
            active_players, adjusted_mmrs)
        
        # Final adjusted MMR update with inflation
        adjusted_mmrs = sum_default_dicts([adjusted_mmrs, inflation.get_inflation_adjustment_deltas()])

        logger.info(
            "RACE_END | total_mmr=%s",
            {k: round(v, 3) for k, v in sorted(adjusted_mmrs.items())},
        )

        # Append race row to table
        table.append({
            "Date": date_str,
            "Race": race_num,
            "Players": players_ordered,
            "Uncertainty Factors": round_dict_values(uncertainty.get_uncertainty_factors().copy(), 2),
            "Race Delta": round_dict_values(ffa_match.get_match_deltas()),
            "Uncertainty Delta": round_dict_values(uncertainty.get_uncertainty_deltas()),
            "Decay Delta": round_dict_values(decay.get_decay_adjustment_deltas()),
            "Decay Inflation Delta": {},
            "Uncertainty Inflation Delta": round_dict_values(inflation.get_inflation_adjustment_deltas().copy()),
            "Total Delta": round_dict_values(sum_dicts([
                total_delta,
                inflation.get_inflation_adjustment_deltas().copy(),
                decay.get_decay_adjustment_deltas()])),
            "Total MMR": round_dict_values(adjusted_mmrs.copy()),
        })

    logger.info("=== MK engine end | sheet=%s | races=%s ===", sheet_name, len(table))

    return table
