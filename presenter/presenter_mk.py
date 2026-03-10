import pandas as pd
from config import MK_BASE_MMR


def expand_table_with_decay_rows(table):
    """
    Insert virtual decay rows before races that have decay effects.
    Returns expanded table with 'Is Decay Row' flag.
    """
    expanded = []
    
    for entry in table:
        # Check if this race has decay effects
        has_decay = any(entry.get("Decay Delta", {}).values())
        
        if has_decay:
            # Calculate pre-race MMR (before race deltas were applied)
            pre_race_mmr = {}
            for player, total_mmr in entry["Total MMR"].items():
                # Subtract race-related deltas to get state after decay but before race
                race_related_delta = (
                    entry.get("Race Delta", {}).get(player, 0) +
                    entry.get("Uncertainty Delta", {}).get(player, 0) +
                    entry.get("Uncertainty Inflation Delta", {}).get(player, 0)
                )
                pre_race_mmr[player] = total_mmr - race_related_delta
            
            # Create virtual decay row
            decay_row_total_delta = {}
            for player in entry["Total MMR"].keys():
                decay_row_total_delta[player] = (
                    entry.get("Decay Delta", {}).get(player, 0) +
                    entry.get("Decay Inflation Delta", {}).get(player, 0)
                )
            
            virtual_row = {
                "Date": entry["Date"],
                "Race": entry["Race"],
                "Players": [],
                "Uncertainty factors": entry["Uncertainty factors"].copy(),
                "Race Delta": {},
                "Uncertainty Delta": {},
                "Decay Delta": entry["Decay Delta"].copy(),
                "Decay Inflation Delta": entry["Decay Inflation Delta"].copy(),
                "Uncertainty Inflation Delta": {},
                "Total Delta": decay_row_total_delta,
                "Total MMR": pre_race_mmr,
                "Is Decay Row": True
            }
            expanded.append(virtual_row)
            
            # Add race row without decay (already shown in virtual row)
            race_row = entry.copy()
            race_row["Decay Delta"] = {}
            race_row["Decay Inflation Delta"] = {}
            race_row["Total Delta"] = {}
            for player in entry["Total MMR"].keys():
                race_row["Total Delta"][player] = (
                    entry.get("Race Delta", {}).get(player, 0) +
                    entry.get("Uncertainty Delta", {}).get(player, 0) +
                    entry.get("Uncertainty Inflation Delta", {}).get(player, 0)
                )
            race_row["Is Decay Row"] = False
            expanded.append(race_row)
        else:
            # No decay, just add the race as-is
            race_row = entry.copy()
            race_row["Is Decay Row"] = False
            expanded.append(race_row)
    
    return expanded


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
    # Expand table with virtual decay rows
    expanded_table = expand_table_with_decay_rows(table)
    
    active_players = list(expanded_table[-1]["Total MMR"].keys())
    current_mmr = {p: MK_BASE_MMR for p in active_players}
    history = [{"Race": 0, **current_mmr}]
    
    race_counter = 0
    for entry in expanded_table:
        current_mmr.update(entry["Total MMR"])
        
        if entry.get("Is Decay Row", False):
            # Decay row gets a fractional position (e.g., 5.5 between race 5 and 6)
            history.append({"Race": race_counter + 0.5, **current_mmr})
        else:
            # Regular race increments counter
            race_counter += 1
            history.append({"Race": race_counter, **current_mmr})
    
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
    """Returns list of race positions where date changes occur (for dashed lines).
    Places lines both at the last race of a date AND at decay rows."""
    expanded_table = expand_table_with_decay_rows(table)
    
    date_change_positions = []
    race_counter = 0
    last_date = None
    
    for i, entry in enumerate(expanded_table):
        current_date = entry["Date"]
        
        if entry.get("Is Decay Row", False):
            # Add line at decay row position (between races)
            date_change_positions.append(race_counter + 0.5)
        else:
            # Regular race
            if last_date is not None and current_date != last_date:
                # Date changed: add line at the previous race (end of old date)
                if race_counter > 0:  # Make sure we have at least one race
                    date_change_positions.append(float(race_counter))
            
            race_counter += 1
            last_date = current_date
    
    return sorted(set(date_change_positions))  # Remove duplicates and sort


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


def prepare_mk_uncertainty_history(table: list) -> pd.DataFrame:
    """Prepare uncertainty history with virtual decay rows."""
    # Expand table with virtual decay rows
    expanded_table = expand_table_with_decay_rows(table)
    
    active_players = set(expanded_table[-1]["Total MMR"].keys())
    
    # Import base uncertainty
    from config import MK_BASE_UNCERTAINTY
    
    # Start with Race 0 at base uncertainty for all players
    initial_unc = {p: MK_BASE_UNCERTAINTY for p in active_players}
    history = [{"Race": 0, **initial_unc}]
    race_counter = 0
    
    for entry in expanded_table:
        # Initialize all players with base uncertainty
        unc = {p: MK_BASE_UNCERTAINTY for p in active_players}
        # Update with actual pre-race values for players who were already active
        unc.update({p: v for p, v in entry["Uncertainty factors"].items() if p in active_players})
        
        if entry.get("Is Decay Row", False):
            # Decay row gets fractional position
            history.append({"Race": race_counter + 0.5, **unc})
        else:
            # Regular race increments counter
            race_counter += 1
            history.append({"Race": race_counter, **unc})

    return pd.DataFrame(history)


def prepare_mk_winrate_matrices(table: list):
    """Calculate head-to-head winrates based on finishing positions.
    Player A beats Player B if A finishes ahead of B in a race."""
    active_players = list(table[-1]["Total MMR"].keys())

    against_m = {p1: {p2: 0 for p2 in active_players} for p1 in active_players}
    against_w = {p1: {p2: 0 for p2 in active_players} for p1 in active_players}
    global_m = {p: 0 for p in active_players}
    global_w = {p: 0 for p in active_players}

    # Original table has no decay rows
    for entry in table:
        players_in_race = entry["Players"]
        n = len(players_in_race)
        
        # For each pair of players in the race
        for i, p1 in enumerate(players_in_race):
            # Count this race for p1
            global_m[p1] += (n - 1)  # p1 competed against (n-1) other players
            
            # p1 beat everyone who finished after them
            wins_this_race = n - i - 1
            global_w[p1] += wins_this_race
            
            # Head-to-head: p1 vs everyone in this race
            for j, p2 in enumerate(players_in_race):
                if i != j:  # Don't count against self
                    against_m[p1][p2] += 1
                    if i < j:  # p1 finished ahead of p2
                        against_w[p1][p2] += 1

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

    # Order players by global winrate and sort matrix accordingly
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
