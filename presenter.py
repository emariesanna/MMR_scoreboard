import pandas as pd
from config import BASE_MMR, PLAYERS

def prepare_match_table(table):
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

        blue_team = entry["Blue Team"]
        orange_team = entry["Orange Team"]
        prob_blue = entry["Blue Win Prob."]
        prob_orange = entry["Orange Win Prob."]

        row_dict = {
            "N.": i,
            "Date": entry["Date"],
            "OT": "✔" if entry["Overtime"] else "",
            "Blue Prob.": f"{int(round(prob_blue * 100))}%",
        }
        for j in range(4):
            row_dict[f"Blue P{j+1}"] = format_player(blue_team[j]) if j < len(blue_team) else ""
        row_dict["Blue Score"] = entry["Blue Score"]
        row_dict["Orange Score"] = entry["Orange Score"]
        for j in range(4):
            row_dict[f"Orange P{j+1}"] = format_player(orange_team[j]) if j < len(orange_team) else ""
        row_dict["Orange Prob."] = f"{int(round(prob_orange * 100))}%"

        display_rows.append(row_dict)

    return pd.DataFrame(display_rows).sort_values("N.", ascending=False).reset_index(drop=True)


def prepare_leaderboard(table):
    last_mmr = table[-1]["Total MMR"]
    s = pd.Series(last_mmr).sort_values(ascending=False).astype(int)
    df = s.reset_index()
    df.columns = ["Player", "MMR"]
    return df


def prepare_mmr_history(table):
    current_mmr = {p: BASE_MMR for p in PLAYERS}
    history = [{"Match": 0, **current_mmr}]

    for i, entry in enumerate(table, start=1):
        current_mmr.update(entry["Total MMR"])
        history.append({"Match": i, **current_mmr})

    return pd.DataFrame(history)


def prepare_uncertainty_history(table):
    history = []
    for i, entry in enumerate(table, start=1):
        record = {"Match": i, **entry["Uncertainty Factors"]}
        history.append(record)

    return pd.DataFrame(history)


def prepare_daily_mmr_delta_history(table):
    last_date = table[-1]["Date"]
    last_day = [e for e in table if e["Date"] == last_date]

    players_in_last_day = set()
    for entry in last_day:
        players_in_last_day.update(entry["Blue Team"] + entry["Orange Team"])

    current_delta = {p: 0.0 for p in players_in_last_day}
    history = [{"Match": 0, **current_delta}]
    for i, entry in enumerate(last_day, start=1):
        for p in players_in_last_day:
            current_delta[p] += entry["Total Delta"][p]
        history.append({"Match": i, **current_delta})

    return pd.DataFrame(history), last_date


def prepare_winrate_matrices(table):

    together_m = {p1: {p2: 0 for p2 in PLAYERS} for p1 in PLAYERS}
    together_w = {p1: {p2: 0 for p2 in PLAYERS} for p1 in PLAYERS}
    against_m  = {p1: {p2: 0 for p2 in PLAYERS} for p1 in PLAYERS}
    against_w  = {p1: {p2: 0 for p2 in PLAYERS} for p1 in PLAYERS}
    global_m   = {p: 0 for p in PLAYERS}
    global_w   = {p: 0 for p in PLAYERS}

    for entry in table:
        blue = entry["Blue Team"]
        orange = entry["Orange Team"]
        blue_won = entry["Blue Score"] > entry["Orange Score"]

        for p in blue:
            global_m[p] += 1
            if blue_won: global_w[p] += 1
        for p in orange:
            global_m[p] += 1
            if not blue_won: global_w[p] += 1

        for p1 in blue:
            for p2 in blue:
                if p1 != p2:
                    together_m[p1][p2] += 1
                    if blue_won: together_w[p1][p2] += 1
        for p1 in orange:
            for p2 in orange:
                if p1 != p2:
                    together_m[p1][p2] += 1
                    if not blue_won: together_w[p1][p2] += 1

        for p1 in blue:
            for p2 in orange:
                against_m[p1][p2] += 1
                if blue_won: against_w[p1][p2] += 1
                against_m[p2][p1] += 1
                if not blue_won: against_w[p2][p1] += 1  

    df_together_w  = pd.DataFrame(index=PLAYERS, columns=PLAYERS, dtype=float)
    df_against_w   = pd.DataFrame(index=PLAYERS, columns=PLAYERS, dtype=float)
    df_together_m = pd.DataFrame(index=PLAYERS, columns=PLAYERS, dtype=float)
    df_against_m  = pd.DataFrame(index=PLAYERS, columns=PLAYERS, dtype=float)

    # Minimum matches threshold for winrate calculation to avoid misleading percentages with very few games played
    MIN_MATCHES = 1

    for p1 in PLAYERS:
        wr_global = (global_w[p1] / global_m[p1]) if global_m[p1] >= MIN_MATCHES else float('nan')
        df_together_w.loc[p1, p1] = wr_global
        df_against_w.loc[p1, p1]  = wr_global
        df_together_m.loc[p1, p1] = global_m[p1] if global_m[p1] >= MIN_MATCHES else float('nan')
        df_against_m.loc[p1, p1]  = global_m[p1] if global_m[p1] >= MIN_MATCHES else float('nan')
        for p2 in PLAYERS:
            if p1 != p2:
                df_together_w.loc[p1, p2]  = (together_w[p1][p2] / together_m[p1][p2]) if together_m[p1][p2] >= MIN_MATCHES else float('nan')
                df_together_m.loc[p1, p2] = together_m[p1][p2] if together_m[p1][p2] >= MIN_MATCHES else float('nan')
                df_against_w.loc[p1, p2]   = (against_w[p1][p2]  / against_m[p1][p2])  if against_m[p1][p2]  >= MIN_MATCHES else float('nan')
                df_against_m.loc[p1, p2]  = against_m[p1][p2]  if against_m[p1][p2]  >= MIN_MATCHES else float('nan')

    # Order players by global winrate and sort matrices accordingly
    df_global_w = pd.Series({p: (global_w[p] / global_m[p]) if global_m[p] >= MIN_MATCHES else float('nan') for p in PLAYERS}, dtype=float)
    sorted_players = df_global_w.sort_values(ascending=False, na_position='last').index.tolist()
    df_together_w  = df_together_w.loc[sorted_players, sorted_players]
    df_against_w   = df_against_w.loc[sorted_players, sorted_players]
    df_together_m = df_together_m.loc[sorted_players, sorted_players]
    df_against_m  = df_against_m.loc[sorted_players, sorted_players]

    return df_together_w, df_against_w, df_together_m, df_against_m


def prepare_date_changes(table):
    return [i + 0.5 for i in range(1, len(table)) if table[i]["Date"] != table[i-1]["Date"]]

