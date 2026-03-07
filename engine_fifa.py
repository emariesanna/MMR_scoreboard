import json
import os
from collections import defaultdict

import pandas as pd

from config import (
    ROOT,
    FIFA_BASE_MMR,
    FIFA_BASE_MMR_DELTA,
    FIFA_BASE_UNCERTAINTY,
    FIFA_HOME_SCORE_COL,
    FIFA_HOME_TEAM_COLS,
    FIFA_DATE_COL,
    FIFA_GAMMA,
    FIFA_GOAL_DIFFERENCE_FACTOR,
    FIFA_MATCH_COL,
    FIFA_MMR_DECAY_PER_DAY,
    FIFA_AWAY_SCORE_COL,
    FIFA_AWAY_TEAM_COLS,
    FIFA_OVERTIME_COL,
    FIFA_PENALTIES_COL,
    FIFA_WINNER_COL,
    FIFA_UNCERTAINTY_DECAY,
    FIFA_UNCERTAINTY_INCREASE,
    FIFA_STARS_HOME_COL,
    FIFA_STARS_AWAY_COL,
    FIFA_RED_HOME_COL,
    FIFA_RED_AWAY_COL,
)
from gsheets import read_sheet_df


def get_fifa_table(sheet_name):
    STAR_RATING_WEIGHT = 40.0
    RED_CARD_WEIGHT = 25.0
    MAX_CONTEXT_MULTIPLIER = 1.25
    MIN_CONTEXT_MULTIPLIER = 0.75
    OVERTIME_GOAL_FACTOR = 0.35
    PENALTIES_GOAL_FACTOR = 0.15
    HOME_FIELD_BONUS = 10.0

    table = []

    active_players = set()
    last_mmr = defaultdict(lambda: FIFA_BASE_MMR)
    last_date = None
    last_date_mmr = defaultdict(lambda: FIFA_BASE_MMR)
    uncertainty_factors = defaultdict(lambda: FIFA_BASE_UNCERTAINTY)

    db = read_sheet_df(sheet_name)

    sort_cols = [c for c in [FIFA_DATE_COL, FIFA_MATCH_COL] if c in db.columns]
    if sort_cols:
        db = db.sort_values(sort_cols).reset_index(drop=True)

    def _safe_bool(value, default=False):
        if pd.isna(value):
            return default
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return bool(value)
        if isinstance(value, str):
            v = value.strip().lower()
            if v in {"true", "1", "yes", "y"}:
                return True
            if v in {"false", "0", "no", "n", ""}:
                return False
        return default

    def _safe_str(value, default=""):
        if pd.isna(value):
            return default
        return str(value).strip()

    def _resolve_result(home_score, away_score, overtime, penalties, winner_raw):
        """
        Returns:
            home_result, away_result, result_label

        home_result / away_result:
            1.0 = win
            0.5 = draw
            0.0 = loss
        """
        if penalties and not overtime:
            overtime = True

        winner = winner_raw.strip().lower()

        if home_score > away_score:
            return 1.0, 0.0, "Home"
        if away_score > home_score:
            return 0.0, 1.0, "Away"

        if not overtime and not penalties:
            return 0.5, 0.5, "Draw"

        if winner == "home":
            return 1.0, 0.0, "Home"
        if winner == "away":
            return 0.0, 1.0, "Away"
        if winner == "draw":
            return 0.5, 0.5, "Draw"

        return 0.5, 0.5, "Draw"

    for _, row in db.iterrows():
        match_delta = {}
        goal_difference_delta = {}
        uncertainty_delta = {}
        decay_delta = {}
        inflation_delta = {}
        total_delta = {}
        total_mmr = {}

        date_val = row[FIFA_DATE_COL]
        date_str = date_val.strftime("%d-%b-%y") if hasattr(date_val, "strftime") else str(date_val)
        match_id = int(row[FIFA_MATCH_COL]) if FIFA_MATCH_COL in row and pd.notna(row[FIFA_MATCH_COL]) else None

        home_team = [p for p in row[FIFA_HOME_TEAM_COLS] if pd.notna(p) and str(p).strip() != ""]
        away_team = [p for p in row[FIFA_AWAY_TEAM_COLS] if pd.notna(p) and str(p).strip() != ""]

        if len(home_team) == 0 or len(away_team) == 0:
            continue

        home_score = int(row[FIFA_HOME_SCORE_COL])
        away_score = int(row[FIFA_AWAY_SCORE_COL])

        overtime = _safe_bool(row[FIFA_OVERTIME_COL]) if FIFA_OVERTIME_COL in row else False
        penalties = _safe_bool(row[FIFA_PENALTIES_COL]) if FIFA_PENALTIES_COL in row else False
        winner_raw = _safe_str(row[FIFA_WINNER_COL]) if FIFA_WINNER_COL in row else ""

        if penalties and not overtime:
            overtime = True

        stars_home = (
            float(row[FIFA_STARS_HOME_COL])
            if FIFA_STARS_HOME_COL in row and pd.notna(row[FIFA_STARS_HOME_COL])
            else 5.0
        )
        stars_away = (
            float(row[FIFA_STARS_AWAY_COL])
            if FIFA_STARS_AWAY_COL in row and pd.notna(row[FIFA_STARS_AWAY_COL])
            else 5.0
        )
        red_home = _safe_bool(row[FIFA_RED_HOME_COL]) if FIFA_RED_HOME_COL in row else False
        red_away = _safe_bool(row[FIFA_RED_AWAY_COL]) if FIFA_RED_AWAY_COL in row else False

        if last_date is not None and date_val != last_date:
            last_date_mmr = defaultdict(lambda: FIFA_BASE_MMR, last_mmr)

        home_size = len(home_team)
        away_size = len(away_team)

        home_base_mmr = sum(last_date_mmr[p] for p in home_team) / home_size
        away_base_mmr = sum(last_date_mmr[p] for p in away_team) / away_size

        star_adjust_home = (stars_home - stars_away) * STAR_RATING_WEIGHT
        star_adjust_away = -star_adjust_home

        red_adjust_home = RED_CARD_WEIGHT * (int(red_away) - int(red_home))
        red_adjust_away = -red_adjust_home

        home_effective_mmr = home_base_mmr + star_adjust_home + red_adjust_home + HOME_FIELD_BONUS
        away_effective_mmr = away_base_mmr + star_adjust_away + red_adjust_away

        home_win_prob = 1 / (1 + 10 ** ((away_effective_mmr - home_effective_mmr) / FIFA_GAMMA))
        away_win_prob = 1 - home_win_prob

        home_result, away_result, winner_label = _resolve_result(
            home_score=home_score,
            away_score=away_score,
            overtime=overtime,
            penalties=penalties,
            winner_raw=winner_raw,
        )

        home_context = 1.0
        away_context = 1.0

        if home_result > away_result:
            home_context += 0.06 * max(0.0, stars_away - stars_home)
            home_context += 0.08 * int(red_home)
        elif home_result < away_result:
            home_context += 0.06 * max(0.0, stars_home - stars_away)
            home_context += 0.08 * int(red_away)

        if away_result > home_result:
            away_context += 0.06 * max(0.0, stars_home - stars_away)
            away_context += 0.08 * int(red_away)
        elif away_result < home_result:
            away_context += 0.06 * max(0.0, stars_away - stars_home)
            away_context += 0.08 * int(red_home)

        home_context = min(MAX_CONTEXT_MULTIPLIER, max(MIN_CONTEXT_MULTIPLIER, home_context))
        away_context = min(MAX_CONTEXT_MULTIPLIER, max(MIN_CONTEXT_MULTIPLIER, away_context))

        base_home_match_delta = FIFA_BASE_MMR_DELTA * (home_result - home_win_prob) * home_context
        base_away_match_delta = FIFA_BASE_MMR_DELTA * (away_result - away_win_prob) * away_context

        pair_delta = (base_home_match_delta - base_away_match_delta) / 2.0
        home_match_delta = pair_delta
        away_match_delta = -pair_delta

        for p in home_team:
            match_delta[p] = home_match_delta / home_size
            last_mmr[p] += match_delta[p]

        for p in away_team:
            match_delta[p] = away_match_delta / away_size
            last_mmr[p] += match_delta[p]

        goal_diff = abs(home_score - away_score)
        gd_factor = goal_diff / FIFA_GOAL_DIFFERENCE_FACTOR[sheet_name] if goal_diff > 0 else 0.0

        if penalties:
            gd_factor *= PENALTIES_GOAL_FACTOR
        elif overtime:
            gd_factor *= OVERTIME_GOAL_FACTOR

        home_goal_diff_delta = (home_match_delta * gd_factor) / home_size
        away_goal_diff_delta = (away_match_delta * gd_factor) / away_size

        for p in home_team:
            goal_difference_delta[p] = home_goal_diff_delta
            last_mmr[p] += home_goal_diff_delta

        for p in away_team:
            goal_difference_delta[p] = away_goal_diff_delta
            last_mmr[p] += away_goal_diff_delta

        # Uncertainty increase due to inactivity + decay
        if last_date is None:
            last_date = date_val
        elif last_date != date_val:
            uncertainty_diff = FIFA_UNCERTAINTY_INCREASE * (date_val - last_date).days

            for p in active_players:
                if uncertainty_factors[p] + uncertainty_diff < FIFA_BASE_UNCERTAINTY:
                    uncertainty_factors[p] = round(uncertainty_factors[p] + uncertainty_diff, 6)
                else:
                    decay_delta[p] = -(
                        (uncertainty_factors[p] + uncertainty_diff - FIFA_BASE_UNCERTAINTY)
                        / FIFA_UNCERTAINTY_INCREASE
                        * FIFA_MMR_DECAY_PER_DAY
                        * last_date_mmr[p]
                    )
                    last_mmr[p] += decay_delta[p]
                    uncertainty_factors[p] = FIFA_BASE_UNCERTAINTY

            last_date = date_val

        pre_match_uncertainty = uncertainty_factors.copy()

        for p in home_team + away_team:
            uncertainty_delta[p] = (match_delta[p] + goal_difference_delta[p]) * (uncertainty_factors[p] - 1)
            last_mmr[p] += uncertainty_delta[p]
            uncertainty_factors[p] = round(
                max(1.0, uncertainty_factors[p] - FIFA_UNCERTAINTY_DECAY[sheet_name]),
                6,
            )

        active_players.update(home_team + away_team)

        # Inflation correction
        inflation = sum(uncertainty_delta.values()) + sum(decay_delta.values())
        denom = sum(last_mmr[p] for p in active_players) if active_players else 1.0

        for p in active_players:
            inflation_delta[p] = -inflation * (last_mmr[p] / denom)
            last_mmr[p] += inflation_delta[p]

        for p in active_players:
            total_delta[p] = (
                match_delta.get(p, 0.0)
                + goal_difference_delta.get(p, 0.0)
                + uncertainty_delta.get(p, 0.0)
                + decay_delta.get(p, 0.0)
                + inflation_delta.get(p, 0.0)
            )
            total_mmr[p] = last_mmr[p]

        table.append({
            "Date": date_str,
            "Match ID": match_id,
            "Home Team": home_team,
            "Away Team": away_team,
            "Home Score": home_score,
            "Away Score": away_score,
            "Overtime": overtime,
            "Penalties": penalties,
            "Winner": winner_label,
            "Stars_home": stars_home,
            "Stars_away": stars_away,
            "Red_home": red_home,
            "Red_away": red_away,
            "Home Effective MMR": round(home_effective_mmr, 3),
            "Away Effective MMR": round(away_effective_mmr, 3),
            "Home Win Prob.": round(home_win_prob, 4),
            "Away Win Prob.": round(away_win_prob, 4),
            "Context Multiplier Home": round(home_context, 4),
            "Context Multiplier Away": round(away_context, 4),
            "Uncertainty Factors": pre_match_uncertainty.copy(),
            "Match Delta": match_delta.copy(),
            "Goal Difference Delta": goal_difference_delta.copy(),
            "Uncertainty Delta": uncertainty_delta.copy(),
            "Decay Delta": decay_delta.copy(),
            "Inflation Delta": inflation_delta.copy(),
            "Total Delta": total_delta.copy(),
            "Total MMR": total_mmr.copy(),
        })

    log_path = os.path.join(ROOT, f"Log_{sheet_name}.json")
    with open(log_path, "w", encoding="utf-8") as f:
        json.dump(table, f, indent=2, ensure_ascii=False, default=str)

    return table