import pandas as pd
import json, os
from collections import defaultdict
from config import (
    ROOT, SPREADSHEET_ID,
    MK_DATE_COL, MK_MATCH_COL, MK_POSITION_COLS,
    MK_BASE_MMR, MK_GAMMA, MK_BASE_MMR_DELTA,
    MK_BASE_UNCERTAINTY, MK_UNCERTAINTY_DECAY, MK_UNCERTAINTY_INCREASE, MK_MMR_DECAY_PER_DAY,
)
from gsheets import read_sheet_df

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

    active_players = set()
    last_mmr = defaultdict(lambda: MK_BASE_MMR)
    last_date = None
    last_date_mmr = defaultdict(lambda: MK_BASE_MMR)
    uncertainty_factors = defaultdict(lambda: MK_BASE_UNCERTAINTY)

    db = read_sheet_df(sheet_name)

    for race_num, (_, row) in enumerate(db.iterrows(), start=1):
        pairwise_delta = {}
        uncertainty_delta = {}
        decay_delta = {}
        inflation_delta = {}
        total_delta = {}
        total_mmr = {}

        date_val = row[MK_DATE_COL]
        date_str = date_val.strftime("%d-%b-%y")

        # Collect finishing order: columns 1st..8th, skip blanks
        players_ordered = [row[col] for col in MK_POSITION_COLS
                           if col in row.index and pd.notna(row[col]) and row[col] != ""]
        n = len(players_ordered)
        if n < 2:
            continue

        # On first race ever, initialise last_date
        if last_date is None:
            last_date = date_val

        # Day boundary: apply inactivity effects and snapshot MMR for win-prob calculations
        if date_val != last_date:
            days_passed = (date_val - last_date).days
            uncertainty_diff = MK_UNCERTAINTY_INCREASE * days_passed
            for p in active_players:
                new_unc = uncertainty_factors[p] + uncertainty_diff
                if new_unc < MK_BASE_UNCERTAINTY:
                    uncertainty_factors[p] = round(new_unc, 6)
                else:
                    excess_days = (new_unc - MK_BASE_UNCERTAINTY) / MK_UNCERTAINTY_INCREASE
                    decay_delta[p] = -excess_days * MK_MMR_DECAY_PER_DAY * last_date_mmr[p]
                    last_mmr[p] += decay_delta[p]
                    uncertainty_factors[p] = MK_BASE_UNCERTAINTY
            last_date_mmr = defaultdict(lambda: MK_BASE_MMR, last_mmr)
            last_date = date_val

        # Pairwise Elo delta
        # For every pair (i, j) where i finishes ahead of j:
        #   S_ij = 1 (i beat j), E_ij = 1/(1+10^((MMR_j-MMR_i)/GAMMA))
        #   contribution = BASE_MMR_DELTA * (S_ij - E_ij) / (n - 1)
        # Normalising by (n-1) keeps the magnitude comparable across field sizes.
        for idx_i, p_i in enumerate(players_ordered):
            delta_i = 0.0
            for idx_j, p_j in enumerate(players_ordered):
                if idx_i == idx_j:
                    continue
                s_ij = 1.0 if idx_i < idx_j else 0.0
                e_ij = 1.0 / (1.0 + 10.0 ** ((last_date_mmr[p_j] - last_date_mmr[p_i]) / MK_GAMMA))
                delta_i += MK_BASE_MMR_DELTA * (s_ij - e_ij) / (n - 1)
            pairwise_delta[p_i] = delta_i
            last_mmr[p_i] += delta_i

        # Uncertainty amplification + decay
        pre_match_uncertainty = uncertainty_factors.copy()
        for p in players_ordered:
            uncertainty_delta[p] = pairwise_delta[p] * (uncertainty_factors[p] - 1)
            last_mmr[p] += uncertainty_delta[p]
            uncertainty_factors[p] = round(
                max(1.0, uncertainty_factors[p] - MK_UNCERTAINTY_DECAY), 6
            )

        # Update active players
        active_players.update(players_ordered)

        # Inflation correction: redistibute the net MMR created by uncertainty+decay
        inflation = sum(uncertainty_delta.values()) + sum(decay_delta.values())
        active_sum = sum(last_mmr[ap] for ap in active_players)
        for p in active_players:
            inflation_delta[p] = -inflation * (last_mmr[p] / active_sum)
            last_mmr[p] += inflation_delta[p]

        for p in active_players:
            total_delta[p] = (
                pairwise_delta.get(p, 0)
                + uncertainty_delta.get(p, 0)
                + decay_delta.get(p, 0)
                + inflation_delta.get(p, 0)
            )
            total_mmr[p] = last_mmr[p]

        table.append({
            "Date": date_str,
            "Race": race_num,
            "Players": players_ordered,
            "Pairwise Delta": pairwise_delta.copy(),
            "Uncertainty Delta": uncertainty_delta.copy(),
            "Decay Delta": decay_delta.copy(),
            "Inflation Delta": inflation_delta.copy(),
            "Total Delta": total_delta.copy(),
            "Uncertainty Factors": pre_match_uncertainty.copy(),
            "Total MMR": total_mmr.copy(),
        })

    log_path = os.path.join(ROOT, f"Log_{sheet_name}.json")
    with open(log_path, "w", encoding="utf-8") as f:
        json.dump(table, f, indent=2, ensure_ascii=False, default=str)

    return table
