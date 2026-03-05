import streamlit as st
import pandas as pd
import altair as alt
from datetime import date

from config import SHEETS_RL, SHEETS_MK, SHEETS_FIFA, MATCH_COL, MK_POSITION_COLS, MK_MATCH_COL
from gsheets import read_sheet_df, append_match, append_mk_race, get_game_players, append_player, read_players_df
from engine import get_table
from engine_mk import get_mk_table
from presenter import prepare_match_table, prepare_leaderboard, prepare_mmr_history, prepare_daily_mmr_delta_history, prepare_uncertainty_history, prepare_winrate_matrices, prepare_date_changes
from presenter_mk import prepare_mk_match_table, prepare_mk_leaderboard, prepare_mk_mmr_history, prepare_mk_daily_mmr_delta_history, prepare_mk_date_changes, prepare_mk_avg_position


def style_winrate(df_val, df_cnt):
    df_text = df_val.copy().astype(object)
    for r in df_val.index:
        for c in df_val.columns:
            v = df_val.loc[r, c]
            df_text.loc[r, c] = "" if pd.isna(v) else f"{v:.0%} ({int(df_cnt.loc[r, c])})"
    return df_text.style.background_gradient(cmap='RdYlGn', vmin=0, vmax=1, gmap=df_val, axis=None)


def plot_line_chart(df_wide, x_col, y_cols, player_colors, vline_x_values=None, tick_values=None):
    domain_colors = [p for p in y_cols if p in player_colors]
    range_colors = [player_colors[p] for p in domain_colors]

    df_long = df_wide.melt(id_vars=[x_col], value_vars=y_cols, var_name="Player", value_name="Value")
    axis_kwargs = dict(format="d", grid=False)
    if tick_values is not None:
        axis_kwargs["values"] = tick_values
    else:
        axis_kwargs["tickMinStep"] = 1
    x_axis = alt.X(f"{x_col}:Q", axis=alt.Axis(**axis_kwargs))

    chart = alt.Chart(df_long).mark_line(point=False).encode(
        x=x_axis,
        y=alt.Y("Value:Q", title="", axis=alt.Axis(grid=True), scale=alt.Scale(zero=False)),
        color=alt.Color("Player:N", scale=alt.Scale(domain=domain_colors, range=range_colors)),
        tooltip=[alt.Tooltip(f"{x_col}:Q", title=x_col), alt.Tooltip("Player:N"), alt.Tooltip("Value:Q")]
    )

    if vline_x_values:
        df_vlines = pd.DataFrame({x_col: vline_x_values})
        rules = alt.Chart(df_vlines).mark_rule(color='gray', strokeDash=[4, 4], opacity=0.5).encode(
            x=f"{x_col}:Q"
        )
        chart = chart + rules

    st.altair_chart(chart, width='stretch')


def render_interface():
    st.set_page_config(page_title="MMR Scoreboard", layout="wide")

    st.sidebar.title("Game")
    selected_game = st.sidebar.radio("Select Game", ["🚀 Rocket League", "🏎️ Mario Kart", "⚽ FIFA"])

    if selected_game == "🚀 Rocket League":
        render_rl()
    elif selected_game == "⚽ FIFA":
        render_fifa()
    else:
        render_mk()


def render_rl():
    st.sidebar.title("Game Mode")
    sheet_labels = [s.removeprefix("RL_") for s in SHEETS_RL]
    selected_label = st.sidebar.radio("Select Mode", sheet_labels)
    selected_sheet = SHEETS_RL[sheet_labels.index(selected_label)]

    rl_players, rl_colors = get_game_players("Rocket League")
    df_matches = read_sheet_df(selected_sheet)

    st.title("🚀 Rocket League - MMR Scoreboard")

    tab1, tab2, tab3 = st.tabs(["📝 Matches", "📈 Charts", "⚽ Add Match"])

    # --- TAB 3: ADD MATCH ---
    with tab3:
        st.subheader("Register New Match")

        with st.expander("➕ Add a new player"):
            with st.form("add_rl_player_form"):
                col_pname, col_pcolor = st.columns([2, 1])
                with col_pname:
                    new_rl_pname = st.text_input("Player name:", key="new_rl_pname")
                with col_pcolor:
                    new_rl_pcolor = st.color_picker("Color:", "#aaaaaa", key="new_rl_pcolor")
                if st.form_submit_button("Add to list"):
                    _name = new_rl_pname.strip()
                    if not _name:
                        st.error("Enter a player name!")
                    elif _name in rl_players:
                        st.warning(f"'{_name}' is already in the list.")
                    else:
                        append_player(_name, ["Rocket League"], new_rl_pcolor)
                        read_players_df.clear()
                        st.success(f"'{_name}' added! Refresh the page to see them.")
                        st.rerun()

        with st.form("new_match_form"):
            col_date, col_extra = st.columns([1, 3])
            with col_date:
                input_date = st.date_input("Date", date.today())
            with col_extra:
                input_overtime = st.checkbox("Overtime?")

            col_blue, col_orange = st.columns(2)

            with col_blue:
                st.info("🔵 BLUE TEAM")
                sel_blue = st.multiselect("Blue Players", options=sorted(rl_players), key="m_blue", max_selections=4)
                score_blue = st.number_input("Blue Goals", min_value=0, step=1, key="s_blue")

            with col_orange:
                st.warning("🟠 ORANGE TEAM")
                sel_orange = st.multiselect("Orange Players", options=sorted(rl_players), key="m_orange", max_selections=4)
                score_orange = st.number_input("Orange Goals", min_value=0, step=1, key="s_orange")

            submitted = st.form_submit_button("REGISTER MATCH", width='stretch')

            if submitted:
                if not sel_blue or not sel_orange:
                    st.error("Select at least one player per team!")
                elif set(sel_blue).intersection(set(sel_orange)):
                    st.error("A player cannot be on both teams!")
                elif score_blue == score_orange:
                    st.error("Draws don't exist in Rocket League!")
                else:
                    last_id = df_matches[MATCH_COL].max() if not df_matches.empty and MATCH_COL in df_matches else 0
                    if pd.isna(last_id):
                        last_id = 0
                    new_id = int(last_id) + 1

                    row_values = [
                        str(input_date),
                        new_id,
                        sel_blue[0] if len(sel_blue) > 0 else "",
                        sel_blue[1] if len(sel_blue) > 1 else "",
                        sel_blue[2] if len(sel_blue) > 2 else "",
                        sel_blue[3] if len(sel_blue) > 3 else "",
                        int(score_blue),
                        int(score_orange),
                        sel_orange[0] if len(sel_orange) > 0 else "",
                        sel_orange[1] if len(sel_orange) > 1 else "",
                        sel_orange[2] if len(sel_orange) > 2 else "",
                        sel_orange[3] if len(sel_orange) > 3 else "",
                        input_overtime,
                    ]
                    append_match(selected_sheet, row_values)
                    read_sheet_df.clear()
                    st.success(f"Match {new_id} registered in {selected_sheet}!")
                    st.rerun()

    if df_matches.empty:
        with tab1:
            st.info(f"No matches recorded in {selected_sheet}. Go to 'Add Match' to get started!")
        with tab2:
            st.info(f"No matches recorded in {selected_sheet}. Go to 'Add Match' to get started!")
        return

    table = get_table(selected_sheet)

    # --- TAB 1: MATCH HISTORY ---
    with tab1:
        st.subheader("Match History")
        st.dataframe(prepare_match_table(table), width='stretch', hide_index=True)

    # --- TAB 2: CHARTS ---
    with tab2:
        st.subheader("Leaderboard & Stats")

        date_changes = prepare_date_changes(table)

        df_mmr = prepare_mmr_history(table)
        st.markdown("#### MMR History (match by match)")
        plot_line_chart(df_mmr, "Match", [c for c in df_mmr.columns if c != "Match"], rl_colors, vline_x_values=date_changes)

        df_unc = prepare_uncertainty_history(table)
        if df_unc is not None:
            st.markdown("#### Uncertainty History")
            plot_line_chart(df_unc, "Match", [c for c in df_unc.columns if c != "Match"], rl_colors)

        col_leaderboard, col_daily = st.columns(2)

        with col_leaderboard:
            df_lb = prepare_leaderboard(table)
            st.markdown("#### Current MMR")
            domain_colors = [p for p in df_lb["Player"] if p in rl_colors]
            range_colors = [rl_colors[p] for p in domain_colors]
            chart = alt.Chart(df_lb).mark_bar().encode(
                x=alt.X("Player", sort="-y"),
                y="MMR",
                color=alt.Color("Player", scale=alt.Scale(domain=domain_colors, range=range_colors), legend=None),
                tooltip=["Player", "MMR"]
            )
            st.altair_chart(chart, width='stretch')

        with col_daily:
            df_daily, last_date = prepare_daily_mmr_delta_history(table)
            st.markdown(f"#### MMR Delta - Last Session ({last_date})")
            if df_daily is not None:
                n_matches = int(df_daily["Match"].max())
                plot_line_chart(df_daily, "Match", [c for c in df_daily.columns if c != "Match"], rl_colors, tick_values=list(range(n_matches + 1)))
            else:
                st.info("No matches played on the last recorded date.")

        st.markdown("---")
        st.subheader("Win Rate Matrices")
        st.markdown(
            "- **Diagonal**: player's overall win rate\n"
            "- **Values in parentheses**: number of matches considered\n"
            "- **Playing Against matrix**: row player's win rate against column player"
        )

        df_tog, df_ag, cnt_tog, cnt_ag = prepare_winrate_matrices(table)

        if df_tog is not None and df_ag is not None:
            col_tog, col_ag = st.columns(2)
            with col_tog:
                st.markdown("#### Win Rate Playing Together")
                st.dataframe(style_winrate(df_tog, cnt_tog))
            with col_ag:
                st.markdown("#### Win Rate Playing Against")
                st.dataframe(style_winrate(df_ag, cnt_ag))
        else:
            st.info("Not enough matches to generate win rate matrices.")


def render_mk():
    selected_sheet = SHEETS_MK[0]  # single MK sheet for now

    mk_players, mk_colors = get_game_players("Mario Kart")
    df_races = read_sheet_df(selected_sheet)

    st.title("🏎️ Mario Kart - MMR Scoreboard")

    tab1, tab2, tab3 = st.tabs(["📝 Races", "📈 Charts", "🏁 Add Race"])

    # --- TAB 3: ADD RACE ---
    with tab3:
        st.subheader("Register New Race")

        with st.expander("➕ Add a new player"):
            with st.form("add_mk_player_form"):
                col_pname, col_pcolor = st.columns([2, 1])
                with col_pname:
                    new_mk_pname = st.text_input("Player name:", key="new_mk_pname")
                with col_pcolor:
                    new_mk_pcolor = st.color_picker("Color:", "#aaaaaa", key="new_mk_pcolor")
                if st.form_submit_button("Add to list"):
                    _name = new_mk_pname.strip()
                    if not _name:
                        st.error("Enter a player name!")
                    elif _name in mk_players:
                        st.warning(f"'{_name}' is already in the list.")
                    else:
                        append_player(_name, ["Mario Kart"], new_mk_pcolor)
                        read_players_df.clear()
                        st.success(f"'{_name}' added! Refresh the page to see them.")
                        st.rerun()

        with st.form("new_mk_race_form"):
            input_date = st.date_input("Date", date.today())
            st.markdown("**Finishing order** (drag to reorder, or enter 1st → last):")
            players_options = sorted(mk_players)

            cols = st.columns(8)
            selected_positions = []
            for i, col in enumerate(cols, start=1):
                with col:
                    p = st.selectbox(f"{i}°", options=[""] + players_options, key=f"mk_p{i}")
                    selected_positions.append(p)

            submitted = st.form_submit_button("REGISTER RACE", width='stretch')

            if submitted:
                ordered = [p for p in selected_positions if p]
                if len(ordered) < 2:
                    st.error("Insert at least 2 players!")
                elif len(ordered) != len(set(ordered)):
                    st.error("The same player appears more than once!")
                else:
                    last_id = df_races[MK_MATCH_COL].max() if not df_races.empty and MK_MATCH_COL in df_races else 0
                    if pd.isna(last_id):
                        last_id = 0
                    new_id = int(last_id) + 1

                    # row: Date, Match ID, 1st, 2nd, ..., 8th
                    row_values = [str(input_date), new_id] + ordered + [""] * (8 - len(ordered))
                    append_mk_race(selected_sheet, row_values)
                    read_sheet_df.clear()
                    st.success(f"Race {new_id} registered!")
                    st.rerun()

    if df_races.empty:
        with tab1:
            st.info("No races recorded yet. Go to 'Add Race' to get started!")
        with tab2:
            st.info("No races recorded yet. Go to 'Add Race' to get started!")
        return

    table = get_mk_table(selected_sheet)

    # --- TAB 1: RACE HISTORY ---
    with tab1:
        st.subheader("Race History")
        st.dataframe(prepare_mk_match_table(table), width='stretch', hide_index=True)

    # --- TAB 2: CHARTS ---
    with tab2:
        st.subheader("Leaderboard & Stats")

        date_changes = prepare_mk_date_changes(table)

        df_mmr = prepare_mk_mmr_history(table)
        st.markdown("#### MMR History (race by race)")
        plot_line_chart(df_mmr, "Race", [c for c in df_mmr.columns if c != "Race"], mk_colors, vline_x_values=date_changes)

        col_leaderboard, col_daily = st.columns(2)

        with col_leaderboard:
            df_lb = prepare_mk_leaderboard(table)
            st.markdown("#### Current MMR")
            domain_colors = [p for p in df_lb["Player"] if p in mk_colors]
            range_colors = [mk_colors[p] for p in domain_colors]
            chart = alt.Chart(df_lb).mark_bar().encode(
                x=alt.X("Player", sort="-y"),
                y="MMR",
                color=alt.Color("Player", scale=alt.Scale(domain=domain_colors, range=range_colors), legend=None),
                tooltip=["Player", "MMR"]
            )
            st.altair_chart(chart, width='stretch')

        with col_daily:
            df_daily, last_date = prepare_mk_daily_mmr_delta_history(table)
            st.markdown(f"#### MMR Delta - Last Session ({last_date})")
            n_races = int(df_daily["Race"].max())
            plot_line_chart(df_daily, "Race", [c for c in df_daily.columns if c != "Race"], mk_colors, tick_values=list(range(n_races + 1)))

        st.markdown("---")
        st.subheader("Average Finishing Position")
        df_avg = prepare_mk_avg_position(table)
        domain_colors = [p for p in df_avg["Player"] if p in mk_colors]
        range_colors = [mk_colors[p] for p in domain_colors]
        chart_avg = alt.Chart(df_avg).mark_bar().encode(
            x=alt.X("Player", sort="y"),
            y=alt.Y("Avg Position", scale=alt.Scale(reverse=False)),
            color=alt.Color("Player", scale=alt.Scale(domain=domain_colors, range=range_colors), legend=None),
            tooltip=["Player", "Avg Position", "Races"]
        )
        st.altair_chart(chart_avg, width='stretch')


def render_fifa():
    selected_sheet = SHEETS_FIFA[0]

    fifa_players, fifa_colors = get_game_players("FIFA")
    df_matches = read_sheet_df(selected_sheet)

    st.title("⚽ FIFA - MMR Scoreboard")

    tab1, tab2, tab3 = st.tabs(["📝 Matches", "📈 Charts", "⚽ Add Match"])

    # --- TAB 3: ADD MATCH ---
    with tab3:
        st.subheader("Register New Match")

        with st.expander("➕ Add a new player"):
            with st.form("add_fifa_player_form"):
                col_pname, col_pcolor = st.columns([2, 1])
                with col_pname:
                    new_fifa_pname = st.text_input("Player name:", key="new_fifa_pname")
                with col_pcolor:
                    new_fifa_pcolor = st.color_picker("Color:", "#aaaaaa", key="new_fifa_pcolor")
                if st.form_submit_button("Add to list"):
                    _name = new_fifa_pname.strip()
                    if not _name:
                        st.error("Enter a player name!")
                    elif _name in fifa_players:
                        st.warning(f"'{_name}' is already in the list.")
                    else:
                        append_player(_name, ["FIFA"], new_fifa_pcolor)
                        read_players_df.clear()
                        st.success(f"'{_name}' added! Refresh the page to see them.")
                        st.rerun()

        with st.form("new_fifa_match_form"):
            col_date, col_extra = st.columns([1, 3])
            with col_date:
                input_date = st.date_input("Date", date.today())
            with col_extra:
                input_overtime = st.checkbox("Extra Time / Penalties?")

            col_home, col_away = st.columns(2)

            with col_home:
                st.info("🏠 HOME")
                sel_home = st.selectbox("Home Player", options=[""] + sorted(fifa_players), key="fifa_home")
                score_home = st.number_input("Home Goals", min_value=0, step=1, key="fifa_s_home")

            with col_away:
                st.warning("✈️ AWAY")
                sel_away = st.selectbox("Away Player", options=[""] + sorted(fifa_players), key="fifa_away")
                score_away = st.number_input("Away Goals", min_value=0, step=1, key="fifa_s_away")

            submitted = st.form_submit_button("REGISTER MATCH", width='stretch')

            if submitted:
                if not sel_home or not sel_away:
                    st.error("Select both players!")
                elif sel_home == sel_away:
                    st.error("Home and Away players must be different!")
                elif score_home == score_away and not input_overtime:
                    st.error("If the score is a draw, check 'Extra Time / Penalties'!")
                else:
                    last_id = df_matches[MATCH_COL].max() if not df_matches.empty and MATCH_COL in df_matches else 0
                    if pd.isna(last_id):
                        last_id = 0
                    new_id = int(last_id) + 1

                    row_values = [
                        str(input_date),
                        new_id,
                        sel_home, "", "", "",   # Blue_1..4
                        int(score_home),
                        int(score_away),
                        sel_away, "", "", "",   # Orange_1..4
                        input_overtime,
                    ]
                    append_match(selected_sheet, row_values)
                    read_sheet_df.clear()
                    st.success(f"Match {new_id} registered!")
                    st.rerun()

    if df_matches.empty:
        with tab1:
            st.info("No matches recorded yet. Go to 'Add Match' to get started!")
        with tab2:
            st.info("No matches recorded yet. Go to 'Add Match' to get started!")
        return

    table = get_table(selected_sheet)

    # --- TAB 1: MATCH HISTORY ---
    with tab1:
        st.subheader("Match History")
        st.dataframe(prepare_match_table(table), width='stretch', hide_index=True)

    # --- TAB 2: CHARTS ---
    with tab2:
        st.subheader("Leaderboard & Stats")

        date_changes = prepare_date_changes(table)

        df_mmr = prepare_mmr_history(table)
        st.markdown("#### MMR History (match by match)")
        plot_line_chart(df_mmr, "Match", [c for c in df_mmr.columns if c != "Match"], fifa_colors, vline_x_values=date_changes)

        df_unc = prepare_uncertainty_history(table)
        if df_unc is not None:
            st.markdown("#### Uncertainty History")
            plot_line_chart(df_unc, "Match", [c for c in df_unc.columns if c != "Match"], fifa_colors)

        col_leaderboard, col_daily = st.columns(2)

        with col_leaderboard:
            df_lb = prepare_leaderboard(table)
            st.markdown("#### Current MMR")
            domain_colors = [p for p in df_lb["Player"] if p in fifa_colors]
            range_colors = [fifa_colors[p] for p in domain_colors]
            chart = alt.Chart(df_lb).mark_bar().encode(
                x=alt.X("Player", sort="-y"),
                y="MMR",
                color=alt.Color("Player", scale=alt.Scale(domain=domain_colors, range=range_colors), legend=None),
                tooltip=["Player", "MMR"]
            )
            st.altair_chart(chart, width='stretch')

        with col_daily:
            df_daily, last_date = prepare_daily_mmr_delta_history(table)
            st.markdown(f"#### MMR Delta - Last Session ({last_date})")
            if df_daily is not None:
                n_matches = int(df_daily["Match"].max())
                plot_line_chart(df_daily, "Match", [c for c in df_daily.columns if c != "Match"], fifa_colors, tick_values=list(range(n_matches + 1)))
            else:
                st.info("No matches played on the last recorded date.")

        st.markdown("---")
        st.subheader("Head-to-Head Win Rate")
        st.markdown(
            "- **Diagonal**: player's overall win rate\n"
            "- **Values in parentheses**: number of matches considered\n"
            "- **Head-to-Head matrix**: row player's win rate against column player"
        )

        _, df_ag, _, cnt_ag = prepare_winrate_matrices(table)

        if df_ag is not None:
            st.dataframe(style_winrate(df_ag, cnt_ag))
        else:
            st.info("Not enough matches to generate head-to-head matrix.")
