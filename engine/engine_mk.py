import pandas as pd
from collections import defaultdict
from config import (
    MK_DATE_COL, MK_MATCH_COL, MK_POSITION_COLS,

    MK_BASE_MMR, MK_GAMMA, MK_BASE_MMR_DELTA, MK_BASE_UNCERTAINTY, MK_UNCERTAINTY_DECAY, 
    MK_UNCERTAINTY_INCREASE, MK_MMR_DECAY_PER_DAY,
)
from gsheets import read_sheet_df
from engine.handlers import (
    InactivityHandler,
    UncertaintyHandler,
    InflationHandler,
    FreeForAllMatchHandler,
)
from utils import format_date, round_dict_values

def get_mk_table(sheet_name: str) -> list:
    # table entry structure:
    # {
    #   "Date": str,
    #   "Race": int,                           # sequential race number
    #   "Players": [str],                      # ordered by finish position (1st to last)
    #   "Pairwise Delta": {str: float},        # MMR delta from pairwise Elo matchups
    #   "Uncertainty Delta": {str: float},     # MMR delta from uncertainty amplification
    #   "Decay Delta": {str: float},           # MMR delta from inactivity decay
    #   "Inflation Delta": {str: float},       # redistribution correction
    #   "Total Delta": {str: float},
    #   "Total MMR": {str: float}
    # }
    table = []

    # Initialize shared state
    active_players = set()
    last_mmr = defaultdict(lambda: MK_BASE_MMR)
    uncertainty_factors = defaultdict(lambda: MK_BASE_UNCERTAINTY)
    last_date_mmr = defaultdict(lambda: MK_BASE_MMR)

    # Initialize handlers
    inactivity = InactivityHandler(active_players, last_mmr, uncertainty_factors, last_date_mmr, 
                                   MK_UNCERTAINTY_INCREASE, MK_MMR_DECAY_PER_DAY, MK_BASE_UNCERTAINTY)
    uncertainty = UncertaintyHandler(last_mmr, uncertainty_factors, MK_UNCERTAINTY_DECAY)
    inflation = InflationHandler(active_players, last_mmr)
    ffa_match = FreeForAllMatchHandler(last_mmr, last_date_mmr, MK_BASE_MMR_DELTA, MK_GAMMA)

    for _, row in read_sheet_df(sheet_name).iterrows():
        # Extract race data
        date_val = pd.to_datetime(row[MK_DATE_COL])
        date_str = format_date(date_val)
        race_num = int(row[MK_MATCH_COL])
        # Collect finishing order: columns 1st..8th, skip blanks
        players_ordered = [row[col] for col in MK_POSITION_COLS
                           if col in row.index and pd.notna(row[col]) and row[col] != ""]
        
        # Process inactivity effects (uncertainty increase and MMR decay)
        decay_delta = inactivity.process_date_change(date_val)
        
        # Calculate decay inflation (separate from uncertainty inflation)
        decay_inflation_delta = inflation.apply_inflation_correction(sum(decay_delta.values()))

        # Calculate position probabilities
        # TODO

        # Apply race outcome
        race_delta = ffa_match.apply_match_outcome(players_ordered)

        # Uncertainty amplification
        pre_race_uncertainty = uncertainty_factors.copy()
        uncertainty_delta = uncertainty.apply_uncertainty_amplification(players_ordered, race_delta)

        # Update active players
        active_players.update(players_ordered)

        # Inflation correction
        uncertainty_inflation_delta = inflation.apply_inflation_correction(sum(uncertainty_delta.values()))

        # Calculate totals
        total_delta = {}
        total_mmr = {}
        for p in active_players:
            total_delta[p] = (
                race_delta.get(p, 0)
                + uncertainty_delta.get(p, 0)
                + decay_delta.get(p, 0)
                + uncertainty_inflation_delta.get(p, 0)
                + decay_inflation_delta.get(p, 0)
            )
            total_mmr[p] = last_mmr[p]

        # Append race row to table (round all deltas and MMR to integers)
        table.append({
            "Date": date_str,
            "Race": race_num,
            "Players": players_ordered,
            "Uncertainty factors": pre_race_uncertainty.copy(),
            "Race Delta": round_dict_values(race_delta),
            "Uncertainty Delta": round_dict_values(uncertainty_delta),
            "Decay Delta": round_dict_values(decay_delta),
            "Decay Inflation Delta": round_dict_values(decay_inflation_delta),
            "Uncertainty Inflation Delta": round_dict_values(uncertainty_inflation_delta),
            "Total Delta": round_dict_values(total_delta),
            "Total MMR": round_dict_values(total_mmr),
        })

    return table
