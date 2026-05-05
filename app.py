import streamlit as st
import pandas as pd
import altair as alt
from datetime import date

from config import RL_SHEETS, MK_SHEET, FIFA_SHEET, RL_MATCH_COL, MK_MATCH_COL, FIFA_MATCH_COL, RL_MATRIX_GAMMA
from gsheets import read_sheet_df, append_match, append_mk_race, get_game_players, append_player, read_players_df
from engine.engine_rl import get_RL_table, UNCERTAINTY
from engine.engine_fifa import get_fifa_table
from engine.engine_mk import get_mk_table
from presenter.presenter_rl import prepare_match_table, prepare_leaderboard, prepare_mmr_history, prepare_daily_mmr_delta_history, prepare_uncertainty_history, prepare_winrate_matrices, prepare_date_changes, prepare_1v1_winrate_matrix, prepare_1v1_goals_matrix, prepare_matrix_mmr_history
from presenter.presenter_mk import prepare_mk_match_table, prepare_mk_leaderboard, prepare_mk_mmr_history, prepare_mk_daily_mmr_delta_history, prepare_mk_date_changes, prepare_mk_avg_position, prepare_mk_uncertainty_history, prepare_mk_winrate_matrices
from presenter.presenter_fifa import prepare_fifa_match_table, prepare_fifa_leaderboard, prepare_fifa_mmr_history, prepare_fifa_daily_mmr_delta_history, prepare_fifa_daily_standings_and_suggested_matches, prepare_fifa_alltime_standings_and_suggested_matches, prepare_fifa_uncertainty_history, prepare_fifa_winrate_matrices, prepare_fifa_goals_matrix, prepare_fifa_date_changes

def style_winrate(df_val, df_cnt):
    df_text = df_val.copy().astype(object)
    for r in df_val.index:
        for c in df_val.columns:
            v = df_val.loc[r, c]
            df_text.loc[r, c] = "" if pd.isna(v) else f"{v:.0%} ({int(df_cnt.loc[r, c])})"
    return df_text.style.background_gradient(cmap='RdYlGn', vmin=0, vmax=1, gmap=df_val, axis=None)


def style_matrix_mmr(df_val, df_delta=None):
    import numpy as np
    
    # Sort players by their diagonal value (overall MMR) descending
    diag_series = pd.Series({p: df_val.loc[p, p] for p in df_val.index if pd.notna(df_val.loc[p, p])})
    sorted_idx = diag_series.sort_values(ascending=False).index.tolist()
    missing = [c for c in df_val.columns if c not in sorted_idx]
    sorted_idx += missing
    
    df_val = df_val.loc[sorted_idx, sorted_idx]
    if df_delta is not None:
        df_delta = df_delta.loc[sorted_idx, sorted_idx]

    df_text = df_val.copy().astype(object)
    gmap = pd.DataFrame(np.nan, index=df_val.index, columns=df_val.columns)
    
    finite_diffs = [abs(float(df_val.loc[r, c])) for r in df_val.index for c in df_val.columns if r != c and pd.notna(df_val.loc[r, c])]
    max_abs_diff = max(finite_diffs) if finite_diffs else 1.0
    
    min_diag = diag_series.min() if not diag_series.empty else 0.0
    max_diag = diag_series.max() if not diag_series.empty else 1.0
    if min_diag == max_diag:
        min_diag -= 1
        max_diag += 1

    for r in df_val.index:
        for c in df_val.columns:
            v = df_val.loc[r, c]
            if pd.isna(v):
                df_text.loc[r, c] = ""
                continue
            
            if r == c:
                df_text.loc[r, c] = f"{int(round(v))}"
                gmap.loc[r, c] = (v - min_diag) / (max_diag - min_diag)
            else:
                diff = v
                sign = "+" if diff > 0 else ""
                df_text.loc[r, c] = f"{sign}{int(round(diff))}" if round(diff) != 0 else "0"
                gmap.loc[r, c] = 0.5 + (v / (2 * max_abs_diff))

            if df_delta is not None and pd.notna(df_delta.loc[r, c]):
                d_val = round(df_delta.loc[r, c])
                if d_val != 0:
                    sign_d = "+" if d_val > 0 else ""
                    df_text.loc[r, c] += f" ({sign_d}{int(d_val)})"

    return df_text.style.background_gradient(
        cmap='RdYlGn',
        vmin=0.0,
        vmax=1.0,
        gmap=gmap,
        axis=None,
    )


def style_goals_matrix(df_val):
    df_text = df_val.copy().astype(object)
    df_diff = pd.DataFrame(index=df_val.index, columns=df_val.columns, dtype=float)

    for r in df_val.index:
        for c in df_val.columns:
            v = df_val.loc[r, c]
            if pd.isna(v):
                df_text.loc[r, c] = ""
                df_diff.loc[r, c] = float("nan")
                continue

            try:
                gf_str, ga_str = str(v).split("-", 1)
                gf = int(gf_str)
                ga = int(ga_str)
            except ValueError:
                df_text.loc[r, c] = str(v)
                df_diff.loc[r, c] = float("nan")
                continue

            if gf == 0 and ga == 0:
                df_text.loc[r, c] = ""
                df_diff.loc[r, c] = float("nan")
                continue

            diff = gf - ga
            sign = "+" if diff > 0 else ""
            df_text.loc[r, c] = f"{gf}-{ga} ({sign}{diff})"
            df_diff.loc[r, c] = diff

    finite_diffs = [abs(float(x)) for x in df_diff.stack() if pd.notna(x)]
    max_abs_diff = max(finite_diffs) if finite_diffs else 1.0

    return df_text.style.background_gradient(
        cmap='RdYlGn',
        vmin=-max_abs_diff,
        vmax=max_abs_diff,
        gmap=df_diff,
        axis=None,
    )


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


@st.cache_data
def get_cached_RL_table(selected_sheet):
    return get_RL_table(selected_sheet)

def render_rl():
    st.sidebar.title("Game Mode")
    sheet_labels = [s.removeprefix("RL_") for s in RL_SHEETS]
    selected_label = st.sidebar.radio("Select Mode", sheet_labels)
    selected_sheet = RL_SHEETS[sheet_labels.index(selected_label)]

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
                    last_id = df_matches[RL_MATCH_COL].max() if not df_matches.empty and RL_MATCH_COL in df_matches else 0
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
                    get_cached_RL_table.clear()
                    st.success(f"Match {new_id} registered in {selected_sheet}!")
                    st.rerun()

    if df_matches.empty:
        with tab1:
            st.info(f"No matches recorded in {selected_sheet}. Go to 'Add Match' to get started!")
        with tab2:
            st.info(f"No matches recorded in {selected_sheet}. Go to 'Add Match' to get started!")
        return

    table = get_cached_RL_table(selected_sheet)

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

        st.markdown("---")
        st.subheader("Matrix MMR Match by Match")
        st.markdown(
            "- **Matrix**: How the row player performs relative to the column player (value > 0 means row player is dominating).\n"
            "- Select a match below to see the state of the MMR Matrix after that match."
        )
        
        matrix_history = prepare_matrix_mmr_history(table)
        if matrix_history:
            if 'matrix_sel' not in st.session_state:
                st.session_state.matrix_sel = len(matrix_history)
                
            def dec_matrix():
                st.session_state.matrix_sel = max(1, st.session_state.matrix_sel - 1)
            def inc_matrix():
                st.session_state.matrix_sel = min(len(matrix_history), st.session_state.matrix_sel + 1)

            col_btn_L, col_sld, col_btn_R = st.columns([1, 10, 1])
            col_btn_L.button("◀", on_click=dec_matrix, use_container_width=True)
            selected_match_idx = col_sld.slider("Select Match Index", min_value=1, max_value=len(matrix_history), key="matrix_sel", label_visibility="collapsed")
            col_btn_R.button("▶", on_click=inc_matrix, use_container_width=True)
            
            entry = table[selected_match_idx - 1]
            ot_str = " **(OT)**" if entry["Overtime"] else ""
            blue_str = ", ".join(entry["Blue Team"])
            orange_str = ", ".join(entry["Orange Team"])

            df_matrix_mmr = matrix_history[selected_match_idx - 1]
            if selected_match_idx > 1:
                df_prev = matrix_history[selected_match_idx - 2]
            else:
                df_prev = pd.DataFrame(0.0, index=df_matrix_mmr.index, columns=df_matrix_mmr.columns)
            
            prob_blue = entry.get("Matrix Blue Prob.", 0.5)
            prob_orange = entry.get("Matrix Orange Prob.", 0.5)
            
            st.markdown(f"🗓️ **Match {entry['Match']}** ({entry['Date']}) — 🔵 {blue_str} **({int(round(prob_blue*100))}%)** **{entry['Blue Score']} - {entry['Orange Score']}** **({int(round(prob_orange*100))}%)** 🟠 {orange_str}{ot_str}")
            
            df_delta = df_matrix_mmr - df_prev
            
            st.dataframe(style_matrix_mmr(df_matrix_mmr, df_delta), use_container_width=True)

        if UNCERTAINTY:
            st.markdown("---")
            df_unc = prepare_uncertainty_history(table)
            st.markdown("#### Uncertainty History")
            plot_line_chart(df_unc, "Match", [c for c in df_unc.columns if c != "Match"], rl_colors, vline_x_values=date_changes)

        st.markdown("---")
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
            n_matches = int(df_daily["Match"].max())
            plot_line_chart(df_daily, "Match", [c for c in df_daily.columns if c != "Match"], rl_colors, tick_values=list(range(n_matches + 1)))

        st.markdown("---")
        st.subheader("Win Rate Matrices")
        st.markdown(
            "- **Diagonal**: player's overall win rate\n"
            "- **Values in parentheses**: number of matches considered\n"
            "- **Playing Against matrix**: row player's win rate against column player"
        )

        df_tog, df_ag, cnt_tog, cnt_ag = prepare_winrate_matrices(table)

        col_tog, col_ag = st.columns(2)
        with col_tog:
            st.markdown("#### Win Rate Playing Together")
            st.dataframe(style_winrate(df_tog, cnt_tog))
        with col_ag:
            st.markdown("#### Win Rate Playing Against")
            st.dataframe(style_winrate(df_ag, cnt_ag))
            
        st.markdown("---")
        st.subheader("1v1 Matrices")
        st.markdown(
            "- **Win Rate 1v1**: win rate playing 1v1 against the column player (row vs col)\n"
            "- **Goals 1v1**: goals scored and conceded in 1v1 matches (row vs col)"
        )
        
        df_1v1_wr, cnt_1v1_wr = prepare_1v1_winrate_matrix(table)
        df_1v1_goals = prepare_1v1_goals_matrix(table)

        col_1v1_wr, col_1v1_goals = st.columns(2)
        with col_1v1_wr:
            st.markdown("#### Win Rate 1v1")
            st.dataframe(style_winrate(df_1v1_wr, cnt_1v1_wr))
        with col_1v1_goals:
            st.markdown("#### Goals 1v1 (GF-GA)")
            st.dataframe(style_goals_matrix(df_1v1_goals))

        st.markdown("---")
        st.subheader("Win Probability vs MMR Difference")
        st.markdown(f"Win probability as a function of $x$ according to $1 / (1 + 10^{{x / {RL_MATRIX_GAMMA}}})$")
        
        import numpy as np
        x_vals = np.linspace(0, int(RL_MATRIX_GAMMA * 2.5), 200)
        y_vals = 1 / (1 + 10**(x_vals / RL_MATRIX_GAMMA))
        df_prob = pd.DataFrame({"x": x_vals, "Prob": y_vals})
        chart_prob = alt.Chart(df_prob).mark_line(color="#1f77b4").encode(
            x=alt.X("x:Q", title="x (Difference)"),
            y=alt.Y("Prob:Q", title="Win Probability", axis=alt.Axis(format="%")),
            tooltip=[alt.Tooltip("x:Q", format=".0f"), alt.Tooltip("Prob:Q", format=".1%")]
        )
        st.altair_chart(chart_prob, width='stretch')

def render_mk():
    selected_sheet = MK_SHEET

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

        st.markdown("---")
        df_unc = prepare_mk_uncertainty_history(table)
        if not df_unc.empty:
            st.markdown("#### Uncertainty History")
            plot_line_chart(df_unc, "Race", [c for c in df_unc.columns if c != "Race"], mk_colors, vline_x_values=date_changes)

        st.markdown("---")
        st.subheader("Head-to-Head Winrates")
        df_ag, cnt_ag = prepare_mk_winrate_matrices(table)
        if not df_ag.empty:
            st.markdown("**Against each other** (% of matchups won)")
            st.dataframe(style_winrate(df_ag, cnt_ag))


def render_fifa():
    selected_sheet = FIFA_SHEET

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
            input_date = st.date_input("Date", date.today())

            col_home, col_away = st.columns(2)

            star_options = [0.5, 1, 1.5, 2, 2.5, 3, 3.5, 4, 4.5, 5]

            with col_home:
                st.info("🏠 HOME")
                sel_home = st.selectbox(
                    "Home Player",
                    options=[""] + sorted(fifa_players),
                    key="fifa_home"
                )
                score_home = st.number_input(
                    "Home Goals",
                    min_value=0,
                    step=1,
                    key="fifa_s_home"
                )
                penalties_home = st.number_input(
                    "Home Penalties Goals",
                    min_value=0,
                    step=1,
                    key="fifa_pen_home",
                    help="Goals scored in penalty shootout (0 if no penalties)"
                )
                stars_home = st.selectbox(
                    "Home Team Stars",
                    options=star_options,
                    index=9,
                    key="fifa_stars_home"
                )

            with col_away:
                st.warning("✈️ AWAY")
                sel_away = st.selectbox(
                    "Away Player",
                    options=[""] + sorted(fifa_players),
                    key="fifa_away"
                )
                score_away = st.number_input(
                    "Away Goals",
                    min_value=0,
                    step=1,
                    key="fifa_s_away"
                )
                penalties_away = st.number_input(
                    "Away Penalties Goals",
                    min_value=0,
                    step=1,
                    key="fifa_pen_away",
                    help="Goals scored in penalty shootout (0 if no penalties)"
                )
                stars_away = st.selectbox(
                    "Away Team Stars",
                    options=star_options,
                    index=9,
                    key="fifa_stars_away"
                )

            submitted = st.form_submit_button("REGISTER MATCH", width="stretch")

            if submitted:
                if not sel_home or not sel_away:
                    st.error("Select both players!")
                elif sel_home == sel_away:
                    st.error("Home and Away players must be different!")
                elif penalties_home != 0 or penalties_away != 0:
                    # Penalty shootout validation
                    if score_home != score_away:
                        st.error("Penalty shootout can only happen when regular score is tied!")
                    elif penalties_home == penalties_away:
                        st.error("Penalty shootout must have a winner!")
                    else:
                        # Valid penalty shootout
                        last_id = (
                            df_matches[FIFA_MATCH_COL].max()
                            if not df_matches.empty and FIFA_MATCH_COL in df_matches
                            else 0
                        )
                        if pd.isna(last_id):
                            last_id = 0
                        new_id = int(last_id) + 1

                        row_values = [
                            str(input_date),
                            new_id,
                            sel_home,
                            sel_away,
                            int(score_home),
                            int(score_away),
                            int(penalties_home),
                            int(penalties_away),
                            float(stars_home),
                            float(stars_away),
                        ]

                        append_match(selected_sheet, row_values)
                        read_sheet_df.clear()
                        st.success(f"Match {new_id} registered!")
                        st.rerun()
                else:
                    # Regular match (no penalties)
                    last_id = (
                        df_matches[FIFA_MATCH_COL].max()
                        if not df_matches.empty and FIFA_MATCH_COL in df_matches
                        else 0
                    )
                    if pd.isna(last_id):
                        last_id = 0
                    new_id = int(last_id) + 1

                    row_values = [
                        str(input_date),
                        new_id,
                        sel_home,
                        sel_away,
                        int(score_home),
                        int(score_away),
                        0,  # Home Penalties Score
                        0,  # Away Penalties Score
                        float(stars_home),
                        float(stars_away),
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

    table = get_fifa_table(selected_sheet)

    # --- TAB 1: MATCH HISTORY ---
    with tab1:
        st.subheader("Match History")
        st.dataframe(
            prepare_fifa_match_table(table),
            width="stretch",
            hide_index=True
        )

    # --- TAB 2: CHARTS ---
    with tab2:
        st.subheader("Leaderboard & Stats")

        all_players = sorted(
            {
                player
                for entry in table
                for player in [entry.get("Home Player"), entry.get("Away Player")]
                if player not in (None, "")
            }
        )
        selected_players = st.multiselect(
            "Filtra classifica all time per giocatori",
            options=all_players,
            default=all_players,
            key="fifa_alltime_players_filter",
        )

        df_standings, df_suggested = prepare_fifa_alltime_standings_and_suggested_matches(
            selected_players,
            table
        )
        st.markdown("#### All-Time Standings & Suggested Matches for Selected Players")
        col_table, col_suggested = st.columns(2)

        with col_table:
            st.markdown("**Football-style table (3-1-0)**")
            if df_standings.empty:
                st.info("No standings available for the selected players.")
            else:
                st.dataframe(df_standings, width="stretch", hide_index=True)

        with col_suggested:
            st.markdown("**Suggested matches (least played pairings)**")
            if df_suggested.empty:
                st.info("At least two selected players are required.")
            else:
                st.dataframe(df_suggested, width="stretch", hide_index=True)

        st.markdown("---")

        col_winrate, col_goals = st.columns(2)

        with col_winrate:
            st.markdown("#### Head-to-Head Win Rate")
            st.markdown(
                "- **Diagonal**: player's overall win rate\n"
                "- **Values in parentheses**: number of matches considered\n"
                "- **Head-to-Head matrix**: row player's win rate against column player"
            )

            df_ag, cnt_ag = prepare_fifa_winrate_matrices(table)
            if df_ag is not None:
                st.dataframe(style_winrate(df_ag, cnt_ag))
            else:
                st.info("Not enough matches to generate head-to-head matrix.")

        with col_goals:
            st.markdown("#### Head-to-Head Goal Difference")
            st.markdown(
                "- **Diagonal**: player's overall goals scored and conceded\n"
                "- **Value in parentheses**: goal difference (goals scored minus goals conceded)\n"
                "- **Head-to-Head matrix**: row player's goal difference against column player"
            )
            st.dataframe(style_goals_matrix(prepare_fifa_goals_matrix(table)))

        st.markdown("---")

        date_changes = prepare_fifa_date_changes(table)

        df_mmr = prepare_fifa_mmr_history(table)
        st.markdown("#### MMR History (match by match)")
        plot_line_chart(
            df_mmr,
            "Match",
            [c for c in df_mmr.columns if c != "Match"],
            fifa_colors,
            vline_x_values=date_changes
        )

        df_unc = prepare_fifa_uncertainty_history(table)
        if df_unc is not None:
            st.markdown("#### Uncertainty History")
            plot_line_chart(
                df_unc,
                "Match",
                [c for c in df_unc.columns if c != "Match"],
                fifa_colors,
                vline_x_values=date_changes
            )

        col_leaderboard, col_daily = st.columns(2)

        with col_leaderboard:
            df_lb = prepare_fifa_leaderboard(table)
            st.markdown("#### Current MMR")

            domain_colors = [p for p in df_lb["Player"] if p in fifa_colors]
            range_colors = [fifa_colors[p] for p in domain_colors]

            chart = alt.Chart(df_lb).mark_bar().encode(
                x=alt.X("Player", sort="-y"),
                y="MMR",
                color=alt.Color(
                    "Player",
                    scale=alt.Scale(domain=domain_colors, range=range_colors),
                    legend=None
                ),
                tooltip=["Player", "MMR"]
            )

            st.altair_chart(chart, width="stretch")

        with col_daily:
            df_daily, last_date = prepare_fifa_daily_mmr_delta_history(table)
            st.markdown(f"#### MMR Delta - Last Session ({last_date})")

            if df_daily is not None:
                n_matches = int(df_daily["Match"].max())
                plot_line_chart(
                    df_daily,
                    "Match",
                    [c for c in df_daily.columns if c != "Match"],
                    fifa_colors,
                    tick_values=list(range(n_matches + 1))
                )
            else:
                st.info("No matches played on the last recorded date.")