import pandas as pd
from config import FIFA_BASE_MMR


def prepare_fifa_match_table(table):
    display_rows = []

    for i, entry in enumerate(table, start=1):
        total_delta = entry["Total Delta"]

        def format_player(player):
            delta = total_delta.get(player, 0)
            delta_int = int(round(delta))
            symbol = "+" if delta_int > 0 else ""
            if delta_int == 0:
                return str(player)
            return f"{player} ({symbol}{delta_int})"

        home_team = entry["Home Team"]
        away_team = entry["Away Team"]
        prob_home = entry["Home Win Prob."]
        prob_away = entry["Away Win Prob."]

        row_dict = {
            "N.": i,
            "Date": entry["Date"],
            "OT": "✔" if entry["Overtime"] else "",
            "Pens": "✔" if entry.get("Penalties", False) else "",
            "Winner": entry.get("Winner", ""),
            "Home Prob.": f"{int(round(prob_home * 100))}%",
            "Home Stars": entry.get("Stars_home", ""),
            "Away Stars": entry.get("Stars_away", ""),
            "Home Red": "✔" if entry.get("Red_home", False) else "",
            "Away Red": "✔" if entry.get("Red_away", False) else "",
        }

        for j in range(4):
            row_dict[f"Home P{j+1}"] = format_player(home_team[j]) if j < len(home_team) else ""

        row_dict["Home Score"] = entry["Home Score"]
        row_dict["Away Score"] = entry["Away Score"]

        for j in range(4):
            row_dict[f"Away P{j+1}"] = format_player(away_team[j]) if j < len(away_team) else ""

        row_dict["Away Prob."] = f"{int(round(prob_away * 100))}%"

        display_rows.append(row_dict)

    return pd.DataFrame(display_rows).sort_values("N.", ascending=False).reset_index(drop=True)


def prepare_fifa_leaderboard(table):
    last_mmr = table[-1]["Total MMR"]
    s = pd.Series(last_mmr).sort_values(ascending=False).astype(int)
    df = s.reset_index()
    df.columns = ["Player", "MMR"]
    return df


def prepare_fifa_mmr_history(table):
    active_players = list(table[-1]["Total MMR"].keys())
    current_mmr = {p: FIFA_BASE_MMR for p in active_players}
    history = [{"Match": 0, **current_mmr}]

    for i, entry in enumerate(table, start=1):
        current_mmr.update(entry["Total MMR"])
        history.append({"Match": i, **current_mmr})

    return pd.DataFrame(history)


def prepare_fifa_uncertainty_history(table):
    active_players = set(table[-1]["Total MMR"].keys())
    history = []

    for i, entry in enumerate(table, start=1):
        unc = {p: v for p, v in entry["Uncertainty Factors"].items() if p in active_players}
        record = {"Match": i, **unc}
        history.append(record)

    return pd.DataFrame(history)


def prepare_fifa_daily_mmr_delta_history(table):
    last_date = table[-1]["Date"]
    last_day = [e for e in table if e["Date"] == last_date]

    players_in_last_day = set()
    for entry in last_day:
        players_in_last_day.update(entry["Home Team"] + entry["Away Team"])

    current_delta = {p: 0.0 for p in players_in_last_day}
    history = [{"Match": 0, **current_delta}]

    for i, entry in enumerate(last_day, start=1):
        for p in players_in_last_day:
            current_delta[p] += entry["Total Delta"].get(p, 0.0)
        history.append({"Match": i, **current_delta})

    return pd.DataFrame(history), last_date


def prepare_fifa_winrate_matrices(table):
    active_players = list(table[-1]["Total MMR"].keys())

    against_m = {p1: {p2: 0 for p2 in active_players} for p1 in active_players}
    against_w = {p1: {p2: 0.0 for p2 in active_players} for p1 in active_players}
    global_m = {p: 0 for p in active_players}
    global_w = {p: 0.0 for p in active_players}

    for entry in table:
        home = entry["Home Team"]
        away = entry["Away Team"]
        winner = entry.get("Winner", "Draw")

        home_won = winner == "Home"
        away_won = winner == "Away"
        draw = winner == "Draw"

        for p in home:
            global_m[p] += 1
            if home_won:
                global_w[p] += 1.0
            elif draw:
                global_w[p] += 0.5

        for p in away:
            global_m[p] += 1
            if away_won:
                global_w[p] += 1.0
            elif draw:
                global_w[p] += 0.5

        for p1 in home:
            for p2 in away:
                against_m[p1][p2] += 1
                against_m[p2][p1] += 1

                if home_won:
                    against_w[p1][p2] += 1.0
                elif away_won:
                    against_w[p2][p1] += 1.0
                else:
                    against_w[p1][p2] += 0.5
                    against_w[p2][p1] += 0.5

    df_against_w = pd.DataFrame(index=active_players, columns=active_players, dtype=float)
    df_against_m = pd.DataFrame(index=active_players, columns=active_players, dtype=float)

    MIN_MATCHES = 1

    for p1 in active_players:
        wr_global = (global_w[p1] / global_m[p1]) if global_m[p1] >= MIN_MATCHES else float("nan")
        df_against_w.loc[p1, p1] = wr_global
        df_against_m.loc[p1, p1] = global_m[p1] if global_m[p1] >= MIN_MATCHES else float("nan")

        for p2 in active_players:
            if p1 != p2:
                df_against_w.loc[p1, p2] = (
                    against_w[p1][p2] / against_m[p1][p2]
                    if against_m[p1][p2] >= MIN_MATCHES else float("nan")
                )
                df_against_m.loc[p1, p2] = (
                    against_m[p1][p2]
                    if against_m[p1][p2] >= MIN_MATCHES else float("nan")
                )

    df_global_w = pd.Series(
        {
            p: (global_w[p] / global_m[p]) if global_m[p] >= MIN_MATCHES else float("nan")
            for p in active_players
        },
        dtype=float
    )

    sorted_players = df_global_w.sort_values(ascending=False, na_position="last").index.tolist()
    df_against_w = df_against_w.loc[sorted_players, sorted_players]
    df_against_m = df_against_m.loc[sorted_players, sorted_players]

    return df_against_w, df_against_m


def prepare_fifa_date_changes(table):
    return [i + 0.5 for i in range(1, len(table)) if table[i]["Date"] != table[i - 1]["Date"]]