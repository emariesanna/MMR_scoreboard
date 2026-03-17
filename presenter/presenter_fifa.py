import pandas as pd
from itertools import combinations
from config import FIFA_BASE_MMR


def expand_table_with_decay_rows(table):
    """
    Insert virtual decay rows before matches that have decay effects.
    Returns expanded table with 'Is Decay Row' flag.
    """
    expanded = []
    
    for entry in table:
        # Check if this match has decay effects
        has_decay = any(entry.get("Decay Delta", {}).values())
        
        if has_decay:
            # Calculate pre-match MMR (before match deltas were applied)
            pre_match_mmr = {}
            for player, total_mmr in entry["Total MMR"].items():
                # Subtract match-related deltas to get state after decay but before match
                match_related_delta = (
                    entry.get("Match Delta", {}).get(player, 0) +
                    entry.get("Goal Difference Delta", {}).get(player, 0) +
                    entry.get("Uncertainty Delta", {}).get(player, 0) +
                    entry.get("Uncertainty Inflation Delta", {}).get(player, 0)
                )
                pre_match_mmr[player] = total_mmr - match_related_delta
            
            # Create virtual decay row
            decay_row_total_delta = {}
            for player in entry["Total MMR"].keys():
                decay_row_total_delta[player] = (
                    entry.get("Decay Delta", {}).get(player, 0) +
                    entry.get("Decay Inflation Delta", {}).get(player, 0)
                )
            
            virtual_row = {
                "Date": entry["Date"],
                "Match": entry["Match"],
                "Home Player": None,
                "Away Player": None,
                "Home Score": None,
                "Away Score": None,
                "Home Penalties Score": None,
                "Away Penalties Score": None,
                "Home team rating": None,
                "Away team rating": None,
                "Home Win Prob.": None,
                "Away Win Prob.": None,
                "Uncertainty Factors": entry["Uncertainty Factors"].copy(),
                "Match Delta": {},
                "Goal Difference Delta": {},
                "Uncertainty Delta": {},
                "Decay Delta": entry["Decay Delta"].copy(),
                "Decay Inflation Delta": entry["Decay Inflation Delta"].copy(),
                "Uncertainty Inflation Delta": {},
                "Total Delta": decay_row_total_delta,
                "Total MMR": pre_match_mmr,
                "Is Decay Row": True
            }
            expanded.append(virtual_row)
            
            # Add match row without decay (already shown in virtual row)
            match_row = entry.copy()
            match_row["Decay Delta"] = {}
            match_row["Decay Inflation Delta"] = {}
            match_row["Total Delta"] = {}
            for player in entry["Total MMR"].keys():
                match_row["Total Delta"][player] = (
                    entry.get("Match Delta", {}).get(player, 0) +
                    entry.get("Goal Difference Delta", {}).get(player, 0) +
                    entry.get("Uncertainty Delta", {}).get(player, 0) +
                    entry.get("Uncertainty Inflation Delta", {}).get(player, 0)
                )
            match_row["Is Decay Row"] = False
            expanded.append(match_row)
        else:
            # No decay, just add the match as-is
            match_row = entry.copy()
            match_row["Is Decay Row"] = False
            expanded.append(match_row)
    
    return expanded


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

        home_player = entry["Home Player"]
        away_player = entry["Away Player"]
        prob_home = entry["Home Win Prob."]
        prob_away = entry["Away Win Prob."]

        # Determine winner
        home_score = entry["Home Score"]
        away_score = entry["Away Score"]
        home_pen_score = entry.get("Home Penalties Score", 0)
        away_pen_score = entry.get("Away Penalties Score", 0)
        
        if home_score > away_score:
            winner = "Home"
        elif away_score > home_score:
            winner = "Away"
        elif home_pen_score > away_pen_score:
            winner = "Home"
        elif away_pen_score > home_pen_score:
            winner = "Away"
        else:
            winner = "Draw"
        
        penalties = home_pen_score != 0 or away_pen_score != 0

        row_dict = {
            "N.": i,
            "Date": entry["Date"],
            "Home Prob.": f"{int(round(prob_home * 100))}%",
            "Home Stars": f"{entry['Home team rating']:.1f}★",
            "Home Player": format_player(home_player),
            "Home Score": home_score,
            "Away Score": away_score,
            "Away Player": format_player(away_player),
            "Away Stars": f"{entry['Away team rating']:.1f}★",
            "Away Prob.": f"{int(round(prob_away * 100))}%",
            "Pens": "✔" if penalties else "",
            "Winner": winner,
        }

        display_rows.append(row_dict)

    return pd.DataFrame(display_rows).sort_values("N.", ascending=False).reset_index(drop=True)


def prepare_fifa_leaderboard(table):
    last_mmr = table[-1]["Total MMR"]
    s = pd.Series(last_mmr).sort_values(ascending=False).astype(int)
    df = s.reset_index()
    df.columns = ["Player", "MMR"]
    return df


def prepare_fifa_mmr_history(table):
    # Expand table with virtual decay rows
    expanded_table = expand_table_with_decay_rows(table)
    
    active_players = list(expanded_table[-1]["Total MMR"].keys())
    current_mmr = {p: FIFA_BASE_MMR for p in active_players}
    history = [{"Match": 0, **current_mmr}]

    match_counter = 0
    for entry in expanded_table:
        current_mmr.update(entry["Total MMR"])
        
        if entry.get("Is Decay Row", False):
            # Decay row gets a fractional position (e.g., 5.5 between match 5 and 6)
            history.append({"Match": match_counter + 0.5, **current_mmr})
        else:
            # Regular match increments counter
            match_counter += 1
            history.append({"Match": match_counter, **current_mmr})

    return pd.DataFrame(history)


def prepare_fifa_uncertainty_history(table):
    active_players = set(table[-1]["Total MMR"].keys())
    
    # Import base uncertainty
    from config import FIFA_BASE_UNCERTAINTY
    
    # Start with Match 0 at base uncertainty for all players
    initial_unc = {p: FIFA_BASE_UNCERTAINTY for p in active_players}
    history = [{"Match": 0, **initial_unc}]

    for i, entry in enumerate(table, start=1):
        # Initialize all players with base uncertainty
        unc = {p: FIFA_BASE_UNCERTAINTY for p in active_players}
        # Update with actual pre-match values for players who were already active
        unc.update({p: v for p, v in entry["Uncertainty Factors"].items() if p in active_players})
        record = {"Match": i, **unc}
        history.append(record)

    return pd.DataFrame(history)


def prepare_fifa_daily_mmr_delta_history(table):
    last_date = table[-1]["Date"]
    last_day = [e for e in table if e["Date"] == last_date]

    players_in_last_day = set()
    for entry in last_day:
        players_in_last_day.add(entry["Home Player"])
        players_in_last_day.add(entry["Away Player"])

    current_delta = {p: 0.0 for p in players_in_last_day}
    history = [{"Match": 0, **current_delta}]

    for i, entry in enumerate(last_day, start=1):
        for p in players_in_last_day:
            current_delta[p] += entry["Total Delta"].get(p, 0.0)
        history.append({"Match": i, **current_delta})

    return pd.DataFrame(history), last_date


def prepare_fifa_daily_standings_and_suggested_matches(table):
    # Per ora inutile
    last_date = table[-1]["Date"]
    last_day = [e for e in table if e["Date"] == last_date]

    players = sorted(
        {
            player
            for entry in last_day
            for player in [entry["Home Player"], entry["Away Player"]]
            if player is not None
        }
    )

    standings = {
        p: {
            "Pts": 0,
            "P": 0,
            "W": 0,
            "D": 0,
            "L": 0,
            "GF": 0,
            "GA": 0,
        }
        for p in players
    }
    played_pairs_count = {tuple(sorted(pair)): 0 for pair in combinations(players, 2)}

    for entry in last_day:
        home_player = entry["Home Player"]
        away_player = entry["Away Player"]
        home_score = int(entry["Home Score"])
        away_score = int(entry["Away Score"])
        home_pen_score = int(entry.get("Home Penalties Score", 0) or 0)
        away_pen_score = int(entry.get("Away Penalties Score", 0) or 0)

        standings[home_player]["P"] += 1
        standings[away_player]["P"] += 1
        standings[home_player]["GF"] += home_score
        standings[home_player]["GA"] += away_score
        standings[away_player]["GF"] += away_score
        standings[away_player]["GA"] += home_score

        if home_score > away_score or (home_score == away_score and home_pen_score > away_pen_score):
            standings[home_player]["W"] += 1
            standings[home_player]["Pts"] += 3
            standings[away_player]["L"] += 1
        elif away_score > home_score or (home_score == away_score and away_pen_score > home_pen_score):
            standings[away_player]["W"] += 1
            standings[away_player]["Pts"] += 3
            standings[home_player]["L"] += 1
        else:
            standings[home_player]["D"] += 1
            standings[away_player]["D"] += 1
            standings[home_player]["Pts"] += 1
            standings[away_player]["Pts"] += 1

        pair_key = tuple(sorted((home_player, away_player)))
        if pair_key in played_pairs_count:
            played_pairs_count[pair_key] += 1

    standings_rows = []
    for player in players:
        row = {"Player": player, **standings[player]}
        row["GD"] = row["GF"] - row["GA"]
        standings_rows.append(row)

    df_standings = pd.DataFrame(standings_rows)
    df_standings = df_standings.sort_values(
        by=["Pts", "GD", "GF", "GA", "Player"],
        ascending=[False, False, False, True, True],
    ).reset_index(drop=True)

    suggested_rows = [
        {
            "Player A": p1,
            "Player B": p2,
            "Played Today": played_pairs_count[(p1, p2)],
        }
        for p1, p2 in combinations(players, 2)
    ]
    df_suggested = pd.DataFrame(suggested_rows)
    if not df_suggested.empty:
        df_suggested = df_suggested.sort_values(
            by=["Played Today", "Player A", "Player B"],
            ascending=[True, True, True],
        ).reset_index(drop=True)

    return df_standings, df_suggested, last_date

def prepare_fifa_alltime_standings_and_suggested_matches(selected_players,table):
    def safe_int(x):
        return int(x) if x not in (None, "", "None") else 0
    
    all_players = sorted(
        {
            player
            for entry in table
            for player in [entry.get("Home Player"), entry.get("Away Player")]
            if player not in (None, "")
        }
    )

    if not selected_players:
        players = all_players
    else:
        players = [p for p in selected_players if p in all_players]

    standings = {
        p: {
            "Pts": 0,
            "P": 0,
            "W": 0,
            "D": 0,
            "L": 0,
            "GF": 0,
            "GA": 0,
        }
        for p in players
    }
    played_pairs_count = {tuple(sorted(pair)): 0 for pair in combinations(players, 2)}

    filtered_matches = []

    for entry in table:
        home_player = entry["Home Player"]
        away_player = entry["Away Player"]

        if not home_player or not away_player:
            continue

        if home_player in players and away_player in players:
            filtered_matches.append(entry)

    for entry in filtered_matches:
        home_player = entry.get("Home Player")
        away_player = entry.get("Away Player")
        home_score = safe_int(entry.get("Home Score"))
        away_score = safe_int(entry.get("Away Score"))
        home_pen_score = safe_int(entry.get("Home Penalties Score", 0))
        away_pen_score = safe_int(entry.get("Away Penalties Score", 0))

        standings[home_player]["P"] += 1
        standings[away_player]["P"] += 1
        standings[home_player]["GF"] += home_score
        standings[home_player]["GA"] += away_score
        standings[away_player]["GF"] += away_score
        standings[away_player]["GA"] += home_score

        if home_score > away_score or (home_score == away_score and home_pen_score > away_pen_score):
            standings[home_player]["W"] += 1
            standings[home_player]["Pts"] += 3
            standings[away_player]["L"] += 1
        elif away_score > home_score or (home_score == away_score and away_pen_score > home_pen_score):
            standings[away_player]["W"] += 1
            standings[away_player]["Pts"] += 3
            standings[home_player]["L"] += 1
        else:
            standings[home_player]["D"] += 1
            standings[away_player]["D"] += 1
            standings[home_player]["Pts"] += 1
            standings[away_player]["Pts"] += 1

        pair_key = tuple(sorted((home_player, away_player)))
        if pair_key in played_pairs_count:
            played_pairs_count[pair_key] += 1

    standings_rows = []
    for player in players:
        row = {"Player": player, **standings[player]}
        row["GD"] = row["GF"] - row["GA"]
        standings_rows.append(row)

    df_standings = pd.DataFrame(standings_rows)

    if not df_standings.empty:
        df_standings = df_standings.sort_values(
            by=["Pts", "GD", "GF", "GA", "Player"],
            ascending=[False, False, False, True, True],
        ).reset_index(drop=True)

    suggested_rows = [
        {
            "Player A": p1,
            "Player B": p2,
            "Played All Time": played_pairs_count[(p1, p2)],
        }
        for p1, p2 in combinations(players, 2)
    ]
    df_suggested = pd.DataFrame(suggested_rows)
    if not df_suggested.empty:
        df_suggested = df_suggested.sort_values(
            by=["Played All Time", "Player A", "Player B"],
            ascending=[True, True, True],
        ).reset_index(drop=True)

    return df_standings, df_suggested

def prepare_fifa_winrate_matrices(table):
    active_players = list(table[-1]["Total MMR"].keys())

    against_m = {p1: {p2: 0 for p2 in active_players} for p1 in active_players}
    against_w = {p1: {p2: 0.0 for p2 in active_players} for p1 in active_players}
    global_m = {p: 0 for p in active_players}
    global_w = {p: 0.0 for p in active_players}

    for entry in table:
        home_player = entry["Home Player"]
        away_player = entry["Away Player"]
        
        # Determine winner
        home_score = entry["Home Score"]
        away_score = entry["Away Score"]
        home_pen_score = entry.get("Home Penalties Score", 0)
        away_pen_score = entry.get("Away Penalties Score", 0)
        
        if home_score > away_score:
            home_won = True
            away_won = False
            draw = False
        elif away_score > home_score:
            home_won = False
            away_won = True
            draw = False
        elif home_pen_score > away_pen_score:
            home_won = True
            away_won = False
            draw = False
        elif away_pen_score > home_pen_score:
            home_won = False
            away_won = True
            draw = False
        else:
            home_won = False
            away_won = False
            draw = True

        # Update global stats
        global_m[home_player] += 1
        if home_won:
            global_w[home_player] += 1.0
        elif draw:
            global_w[home_player] += 0.5

        global_m[away_player] += 1
        if away_won:
            global_w[away_player] += 1.0
        elif draw:
            global_w[away_player] += 0.5

        # Update head-to-head stats
        against_m[home_player][away_player] += 1
        against_m[away_player][home_player] += 1

        if home_won:
            against_w[home_player][away_player] += 1.0
        elif away_won:
            against_w[away_player][home_player] += 1.0
        else:  # draw
            against_w[home_player][away_player] += 0.5
            against_w[away_player][home_player] += 0.5

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


def prepare_fifa_goals_matrix(table):
    active_players = list(table[-1]["Total MMR"].keys())

    total_gf = {p: 0 for p in active_players}
    total_ga = {p: 0 for p in active_players}
    h2h_gf = {p1: {p2: 0 for p2 in active_players} for p1 in active_players}
    h2h_ga = {p1: {p2: 0 for p2 in active_players} for p1 in active_players}

    for entry in table:
        home_player = entry["Home Player"]
        away_player = entry["Away Player"]
        home_score = int(entry["Home Score"])
        away_score = int(entry["Away Score"])

        total_gf[home_player] += home_score
        total_ga[home_player] += away_score
        total_gf[away_player] += away_score
        total_ga[away_player] += home_score

        h2h_gf[home_player][away_player] += home_score
        h2h_ga[home_player][away_player] += away_score
        h2h_gf[away_player][home_player] += away_score
        h2h_ga[away_player][home_player] += home_score

    df_goals = pd.DataFrame(index=active_players, columns=active_players, dtype=object)

    for p1 in active_players:
        for p2 in active_players:
            if p1 == p2:
                gf = total_gf[p1]
                ga = total_ga[p1]
            else:
                gf = h2h_gf[p1][p2]
                ga = h2h_ga[p1][p2]
            df_goals.loc[p1, p2] = f"{gf}-{ga}"

    goal_diff_rank = pd.Series({p: total_gf[p] - total_ga[p] for p in active_players}, dtype=float)
    sorted_players = goal_diff_rank.sort_values(ascending=False).index.tolist()
    df_goals = df_goals.loc[sorted_players, sorted_players]

    return df_goals


def prepare_fifa_date_changes(table):
    """Returns list of match positions where date changes occur (for dashed lines).
    Places lines both at the last match of a date AND at decay rows."""
    expanded_table = expand_table_with_decay_rows(table)
    
    date_change_positions = []
    match_counter = 0
    last_date = None
    
    for i, entry in enumerate(expanded_table):
        current_date = entry["Date"]
        
        if entry.get("Is Decay Row", False):
            # Add line at decay row position (between matches)
            date_change_positions.append(match_counter + 0.5)
        else:
            # Regular match
            if last_date is not None and current_date != last_date:
                # Date changed: add line at the previous match (end of old date)
                if match_counter > 0:  # Make sure we have at least one match
                    date_change_positions.append(float(match_counter))
            
            match_counter += 1
            last_date = current_date
    
    return sorted(set(date_change_positions))  # Remove duplicates and sort