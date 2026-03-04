import streamlit as st
import pandas as pd
import altair as alt
from datetime import date

from config import PLAYERS, SHEETS, DATE_COL, MATCH_COL, BLUE_TEAM_COLS, ORANGE_TEAM_COLS, BLUE_SCORE_COL, ORANGE_SCORE_COL, OVERTIME_COL, PLAYER_COLORS
from gsheets import read_sheet_df, append_match
from engine import get_table
from presenter import prepare_match_table, prepare_leaderboard, prepare_mmr_history, prepare_daily_mmr_delta_history, prepare_uncertainty_history, prepare_winrate_matrices, prepare_date_changes


def style_winrate(df_val, df_cnt):
    df_text = df_val.copy().astype(object)
    for r in df_val.index:
        for c in df_val.columns:
            v = df_val.loc[r, c]
            df_text.loc[r, c] = "" if pd.isna(v) else f"{v:.0%} ({int(df_cnt.loc[r, c])})"
    return df_text.style.background_gradient(cmap='RdYlGn', vmin=0, vmax=1, gmap=df_val, axis=None)


def plot_line_chart(df_wide, x_col, y_cols, vline_x_values=None, tick_values=None):
    domain_colors = list(PLAYER_COLORS.keys())
    range_colors = list(PLAYER_COLORS.values())

    df_long = df_wide.melt(id_vars=[x_col], value_vars=y_cols, var_name="Player", value_name="Value")
    axis_kwargs = dict(format="d", grid=False)
    if tick_values is not None:
        axis_kwargs["values"] = tick_values
    else:
        axis_kwargs["tickMinStep"] = 1
    x_axis = alt.X(f"{x_col}:Q", axis=alt.Axis(**axis_kwargs))

    chart = alt.Chart(df_long).mark_line(point=False).encode(
        x=x_axis,
        y=alt.Y("Value:Q", title="", axis=alt.Axis(grid=True)),
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
    st.set_page_config(page_title="Rocket League MMR", layout="wide")

    st.sidebar.title("Game Mode")
    selected_sheet = st.sidebar.radio("Select Mode", SHEETS)

    df_matches = read_sheet_df(selected_sheet)

    st.title("🏎️ Rocket League - MMR Scoreboard")

    tab1, tab2, tab3 = st.tabs(["📝 Matches", "📈 Charts", "⚽ Add Match"])

    # --- TAB 3: ADD MATCH ---
    with tab3:
        st.subheader("Register New Match")
        with st.form("new_match_form"):
            col_date, col_extra = st.columns([1, 3])
            with col_date:
                input_date = st.date_input("Date", date.today())
            with col_extra:
                input_overtime = st.checkbox("Overtime?")

            col_blue, col_orange = st.columns(2)

            with col_blue:
                st.info("🔵 BLUE TEAM")
                sel_blue = st.multiselect("Blue Players", options=sorted(PLAYERS), key="m_blue", max_selections=4)
                score_blue = st.number_input("Blue Goals", min_value=0, step=1, key="s_blue")

            with col_orange:
                st.warning("🟠 ORANGE TEAM")
                sel_orange = st.multiselect("Orange Players", options=sorted(PLAYERS), key="m_orange", max_selections=4)
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

        # MMR history (match by match)
        df_mmr = prepare_mmr_history(table)
        st.markdown("#### MMR History (match by match)")
        plot_line_chart(df_mmr, "Match", [c for c in df_mmr.columns if c != "Match"], vline_x_values=date_changes)

        # Uncertainty history
        df_unc = prepare_uncertainty_history(table)
        if df_unc is not None:
            st.markdown("#### Uncertainty History")
            plot_line_chart(df_unc, "Match", [c for c in df_unc.columns if c != "Match"])

        col_leaderboard, col_daily = st.columns(2)

        # Current leaderboard bar chart
        with col_leaderboard:
            df_lb = prepare_leaderboard(table)
            st.markdown("#### Current MMR")
            domain_colors = list(PLAYER_COLORS.keys())
            range_colors = list(PLAYER_COLORS.values())
            chart = alt.Chart(df_lb).mark_bar().encode(
                x=alt.X("Player", sort="-y"),
                y="MMR",
                color=alt.Color("Player", scale=alt.Scale(domain=domain_colors, range=range_colors), legend=None),
                tooltip=["Player", "MMR"]
            )
            st.altair_chart(chart, width='stretch')

        # Daily MMR delta
        with col_daily:
            df_daily, last_date = prepare_daily_mmr_delta_history(table)
            st.markdown(f"#### MMR Delta - Last Session ({last_date})")
            if df_daily is not None:
                n_matches = int(df_daily["Match"].max())
                plot_line_chart(df_daily, "Match", [c for c in df_daily.columns if c != "Match"], tick_values=list(range(n_matches + 1)))
            else:
                st.info("No matches played on the last recorded date.")

        # Win rate matrices
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
