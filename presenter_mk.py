import pandas as pd
from config import MK_BASE_MMR


def prepare_mk_match_table(table: list) -> pd.DataFrame:
    rows = []
    for entry in table:
        players = entry["Players"]
        total_delta = entry["Total Delta"]
        n = len(players)

        def fmt(p, pos):
            delta = total_delta.get(p, 0)
            d = int(round(delta))
            symbol = "+" if d > 0 else ""
            suffix = f" ({symbol}{d})" if d != 0 else ""
            return f"{pos}. {p}{suffix}"

        row = {
            "N.": entry["Race"],
            "Date": entry["Date"],
        }
        for i, p in enumerate(players, start=1):
            row[f"P{i}"] = fmt(p, i)
        # pad missing slots
        for i in range(len(players) + 1, 9):
            row[f"P{i}"] = ""
        rows.append(row)

    return pd.DataFrame(rows).sort_values("N.", ascending=False).reset_index(drop=True)


def prepare_mk_leaderboard(table: list) -> pd.DataFrame:
    last_mmr = table[-1]["Total MMR"]
    s = pd.Series(last_mmr).sort_values(ascending=False).astype(int)
    df = s.reset_index()
    df.columns = ["Player", "MMR"]
    return df


def prepare_mk_mmr_history(table: list) -> pd.DataFrame:
    active_players = list(table[-1]["Total MMR"].keys())
    current_mmr = {p: MK_BASE_MMR for p in active_players}
    history = [{"Race": 0, **current_mmr}]
    for entry in table:
        current_mmr.update(entry["Total MMR"])
        history.append({"Race": entry["Race"], **current_mmr})
    return pd.DataFrame(history)


def prepare_mk_daily_mmr_delta_history(table: list):
    last_date = table[-1]["Date"]
    last_day = [e for e in table if e["Date"] == last_date]

    players_in_last_day = set()
    for entry in last_day:
        players_in_last_day.update(entry["Players"])

    current_delta = {p: 0.0 for p in players_in_last_day}
    history = [{"Race": 0, **current_delta}]
    for i, entry in enumerate(last_day, start=1):
        for p in players_in_last_day:
            current_delta[p] += entry["Total Delta"].get(p, 0)
        history.append({"Race": i, **current_delta})

    return pd.DataFrame(history), last_date


def prepare_mk_date_changes(table: list) -> list:
    return [i + 0.5 for i in range(1, len(table)) if table[i]["Date"] != table[i - 1]["Date"]]


def prepare_mk_avg_position(table: list) -> pd.DataFrame:
    """Average finishing position per player (lower = better)."""
    totals = {}
    counts = {}
    for entry in table:
        for pos, p in enumerate(entry["Players"], start=1):
            totals[p] = totals.get(p, 0) + pos
            counts[p] = counts.get(p, 0) + 1
    rows = [
        {"Player": p, "Avg Position": round(totals[p] / counts[p], 2), "Races": counts[p]}
        for p in totals
    ]
    return pd.DataFrame(rows).sort_values("Avg Position").reset_index(drop=True)
