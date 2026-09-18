"""Pairwise Bradley-Terry ranking engine.

The public ``calculate_ranking`` function is deliberately independent from
Google Sheets.  ``get_RL_table`` is the compatibility adapter used by the
existing Rocket League input format.
"""

from __future__ import annotations

from collections import defaultdict
from math import log, sqrt

import pandas as pd

from config import (
	RL_BLUE_SCORE_COL,
	RL_BLUE_TEAM_COLS,
	RL_DATE_COL,
	RL_DEACTIVATED_PLAYERS,
	RL_MATCH_COL,
	RL_ORANGE_SCORE_COL,
	RL_ORANGE_TEAM_COLS,
	RL_OVERTIME_COL,
)
from gsheets import read_sheet_df
from utils import convert_bool, format_date, round_dict_values

RL_BASE_MMR = 2000
RL_MMR_SCALE = 1000
UNCERTAINTY = True


def _number(value, default=0.0):
	"""Convert a value to float, returning a fallback for missing/invalid data.

	Args:
		value: Value to convert.
		default: Value returned when conversion is not possible.

	Returns:
		The converted float or ``default``.
	"""
	try:
		if pd.isna(value):
			return default
		return float(value)
	except (TypeError, ValueError):
		return default


def _match_weight(goal_a, goal_b, overtime, overtime_factor, margin_cap):
	"""Calculate a match weight from overtime and goal difference.

	Args:
		goal_a: Goals scored by team A.
		goal_b: Goals scored by team B.
		overtime: Whether the match ended in overtime.
		overtime_factor: Multiplier applied to overtime matches.
		margin_cap: Goal difference at which the margin multiplier saturates.

	Returns:
		The multiplicative weight for the match.
	"""
	difference = min(abs(goal_a - goal_b), margin_cap)
	margin_factor = 1.0 if difference <= 0 else 1.0 + (difference - 1.0) / (margin_cap - 1.0)
	return (overtime_factor if overtime else 1.0) * margin_factor


def _ordered_matches(matches):
	"""Order matches chronologically while preserving input order on ties.

	Args:
		matches: Iterable of match dictionaries with an optional ``timestamp``.

	Returns:
		A list of ``(original_index, match)`` pairs in chronological order.
	"""
	return sorted(
		enumerate(matches),
		key=lambda item: (item[1].get("timestamp", item[0]), item[0]),
	)


def _team_strength(team, strengths):
	"""Combine player strengths into a team strength using a linear sum.

	Args:
		team: Iterable of player names.
		strengths: Mapping from player name to positive latent strength.

	Returns:
		The aggregated team strength.

	Raises:
		ValueError: If the team is empty.
	"""
	team_strengths = [strengths[player] for player in team]
	if not team_strengths:
		raise ValueError("team must contain at least one player")
	return sum(team_strengths)


def predict_win_probability(team_a, team_b, previous_result=None):
	"""Predict the pre-match win probability for two teams.

	Args:
		team_a: Iterable of players on team A.
		team_b: Iterable of players on team B.
		previous_result: Optional ranking snapshot used for player strengths.

	Returns:
		A ``(probability_a, probability_b)`` tuple. Unknown players use neutral
		strength ``1.0``.
	"""
	players = list(team_a) + list(team_b)
	strengths = {player: 1.0 for player in players}
	if previous_result is not None:
		previous_strengths = previous_result.get(
			"strength",
			previous_result.get("Strength", {}),
		)
		strengths.update({
			player: previous_strengths.get(player, 1.0)
			for player in players
		})
	strength_a = _team_strength(team_a, strengths)
	strength_b = _team_strength(team_b, strengths)
	probability_a = strength_a / (strength_a + strength_b)
	return probability_a, 1.0 - probability_a


def _build_pairwise(matches, discount_base):
	"""Expand matches into normalized discounted pairwise win weights.

	Args:
		matches: Normalized match dictionaries containing ``team_A`` and ``team_B``.
		discount_base: Exponential discount base for older direct encounters.

	Each player's contribution is normalized by the number of opponents in the
	other team. Consequently, every player contributes one match weight in
	 total, regardless of team size.

	Returns:
		A tuple containing the sorted player list and a nested raw wins mapping.
	"""
	players = sorted({p for match in matches for team in ("team_A", "team_B") for p in match[team]})
	pair_counts = defaultdict(int)
	for match in matches:
		for player_a in match["team_A"]:
			for player_b in match["team_B"]:
				pair_counts[tuple(sorted((player_a, player_b)))] += 1

	wins = {player: defaultdict(float) for player in players}
	seen_pairs = defaultdict(int)
	for _, match in _ordered_matches(matches):
		goal_a = _number(match.get("goal_A"))
		goal_b = _number(match.get("goal_B"))
		weight = _match_weight(
			goal_a,
			goal_b,
			bool(match.get("overtime", False)),
			match.get("overtime_factor", 0.5),
			match.get("margin_cap", 6.0),
		)
		winner = match.get("winner")
		if winner not in ("A", "B"):
			winner = "A" if goal_a > goal_b else "B"
		winning_team = match["team_A"] if winner == "A" else match["team_B"]
		losing_team = match["team_B"] if winner == "A" else match["team_A"]
		for player_a in winning_team:
			for player_b in losing_team:
				pair = tuple(sorted((player_a, player_b)))
				exponent = pair_counts[pair] - seen_pairs[pair] - 1
				pair_weight = (weight / len(losing_team)) * (discount_base ** exponent)
				wins[player_a][player_b] += pair_weight
				seen_pairs[pair] += 1

	return players, wins


def _update_pairwise_state(match, players, wins, discount_base):
	"""Add one chronological match to an existing pairwise state.

	Args:
		match: Normalized match dictionary.
		players: Mutable list of known players.
		wins: Mutable nested pairwise win-weight mapping.
		discount_base: Discount applied to the previous value of each replayed pair.

	Returns:
		The updated ``players`` list and ``wins`` mapping.

	The update is equivalent to rebuilding the historical pair weights: only
	pairs that meet in this match are discounted, because the discount is
	pairwise rather than global.
	"""
	for player in match["team_A"] + match["team_B"]:
		if player not in players:
			players.append(player)
		wins.setdefault(player, defaultdict(float))

	goal_a = _number(match.get("goal_A"))
	goal_b = _number(match.get("goal_B"))
	weight = _match_weight(
		goal_a,
		goal_b,
		bool(match.get("overtime", False)),
		match.get("overtime_factor", 0.5),
		match.get("margin_cap", 6.0),
	)
	winner = match.get("winner")
	if winner not in ("A", "B"):
		winner = "A" if goal_a > goal_b else "B"
	winning_team = match["team_A"] if winner == "A" else match["team_B"]
	losing_team = match["team_B"] if winner == "A" else match["team_A"]

	for winning_player in winning_team:
		for losing_player in losing_team:
			wins[winning_player][losing_player] *= discount_base
			wins[losing_player][winning_player] *= discount_base
			wins[winning_player][losing_player] += weight / len(losing_team)

	return players, wins


def _solve_zermelo(players, wins, tolerance, max_iterations, initial_strengths=None):
	"""Estimate normalized Bradley-Terry strengths with Zermelo iteration.

	Args:
		players: Players included in the model.
		wins: Pairwise win weights, including smoothing if requested.
		tolerance: Maximum strength change accepted as convergence.
		max_iterations: Safety limit for the iteration count.
		initial_strengths: Optional positive strengths used as the initial guess.

	Returns:
		A mapping from player name to positive strength with mean strength one.
	"""
	strengths = {
		player: max(float((initial_strengths or {}).get(player, 1.0)), 1e-12)
		for player in players
	}
	for _ in range(max_iterations):
		updated = {}
		for player in players:
			total_wins = sum(wins[player].values())
			denominator = sum(
				(wins[player].get(opponent, 0.0) + wins[opponent].get(player, 0.0))
				/ (strengths[player] + strengths[opponent])
				for opponent in players
				if opponent != player
			)
			updated[player] = total_wins / denominator if denominator else strengths[player]
		scale = sum(updated.values()) / len(updated) if updated else 1.0
		updated = {player: value / scale for player, value in updated.items()}
		if max((abs(updated[p] - strengths[p]) for p in players), default=0.0) < tolerance:
			strengths = updated
			break
		strengths = updated
	return strengths


def calculate_ranking(
	matches,
	*,
	k=1.0,
	overtime_factor=0.5,
	margin_cap=6.0,
	discount_base=0.98,
	smoothing=1.0,
	tolerance=1e-6,
	max_iterations=10000,
	_raw_pairwise=None,
	_raw_players=None,
	_initial_strengths=None,
):
	"""Recalculate the complete ranking from a list of match dictionaries.

	Args:
		matches: Match dictionaries accepting ``team_A``, ``team_B``, ``winner``,
			``goal_A``, ``goal_B``, ``overtime`` and ``timestamp``.
		k: Conservativeness multiplier applied to uncertainty.
		overtime_factor: Weight multiplier for overtime matches.
		margin_cap: Maximum goal difference used by the margin factor.
		discount_base: Pairwise temporal discount base.
		smoothing: Synthetic win/loss weight added to every player pair.
		tolerance: Zermelo convergence threshold.
		max_iterations: Maximum number of Zermelo iterations.
		_raw_pairwise: Internal precomputed pairwise state for incremental updates.
		_raw_players: Internal player list corresponding to ``_raw_pairwise``.
		_initial_strengths: Internal warm-start values for Zermelo.

	Returns:
		A dictionary containing ranking rows, strengths, theta, sigma, scores,
		an ordered ranking triple for each player, and the unsmoothed direct
		pairwise results and victory matrix.
	"""
	if _raw_pairwise is None:
		normalized = [
			{**match, "team_A": list(dict.fromkeys(match.get("team_A", []))),
			 "team_B": list(dict.fromkeys(match.get("team_B", []))),
			 "overtime_factor": overtime_factor, "margin_cap": margin_cap}
			for match in matches
		]
		players, raw_wins = _build_pairwise(normalized, discount_base)
	else:
		players = list(_raw_players or [])
		raw_wins = _raw_pairwise
	corrected = {
		player: {
			opponent: (raw_wins[player].get(opponent, 0.0) + smoothing)
			for opponent in players if opponent != player
		}
		for player in players
	}
	strengths = _solve_zermelo(
		players,
		corrected,
		tolerance,
		max_iterations,
		initial_strengths=_initial_strengths,
	)
	mean_theta = sum(log(strengths[player]) for player in players) / len(players) if players else 0.0
	theta = {player: log(strengths[player]) - mean_theta for player in players}
	information = {}
	for player in players:
		value = 0.0
		for opponent in players:
			if opponent == player:
				continue
			total = corrected[player][opponent] + corrected[opponent][player]
			probability = strengths[player] / (strengths[player] + strengths[opponent])
			value += total * probability * (1.0 - probability)
		information[player] = value
	sigma = {player: 1.0 / sqrt(value) if value > 0 else float("inf") for player, value in information.items()}
	score = {player: theta[player] - k * sigma[player] for player in players}
	mmr_triples = {
		player: {
			"mmr_minus_3sigma": RL_BASE_MMR + RL_MMR_SCALE * (theta[player] - 3.0 * sigma[player]),
			"mmr_score": RL_BASE_MMR + RL_MMR_SCALE * score[player],
			"mmr_plus_3sigma": RL_BASE_MMR + RL_MMR_SCALE * (theta[player] + 3.0 * sigma[player]),
		}
		for player in players
	}
	ranking_triples = sorted(
		[
			{
				"player": player,
				"theta_minus_3sigma": theta[player] - 3.0 * sigma[player],
				"theta_minus_k_sigma": score[player],
				"theta_plus_3sigma": theta[player] + 3.0 * sigma[player],
				**mmr_triples[player],
			}
			for player in players
		],
		key=lambda item: item["theta_minus_k_sigma"],
		reverse=True,
	)
	direct = {
		player: {
			opponent: {
				"weight": raw_wins[player].get(opponent, 0.0),
				"probability": (
					raw_wins[player].get(opponent, 0.0)
					/ (raw_wins[player].get(opponent, 0.0) + raw_wins[opponent].get(player, 0.0))
					if raw_wins[player].get(opponent, 0.0) + raw_wins[opponent].get(player, 0.0) else None
				),
			}
			for opponent in players if opponent != player and (
				raw_wins[player].get(opponent, 0.0) or raw_wins[opponent].get(player, 0.0)
			)
		}
		for player in players
	}
	probability_matrix = {
		"players": players,
		"values": [
			[
				None if player == opponent else (
					raw_wins[player].get(opponent, 0.0)
					/ (raw_wins[player].get(opponent, 0.0) + raw_wins[opponent].get(player, 0.0))
					if raw_wins[player].get(opponent, 0.0) + raw_wins[opponent].get(player, 0.0)
					else None
				)
				for opponent in players
			]
			for player in players
		],
	}
	return {
		"ranking": sorted(
			[{"player": player, "theta": theta[player], "sigma": sigma[player], "score": score[player]}
			 for player in players],
			key=lambda item: item["score"], reverse=True,
		),
		"players": players,
		"theta": theta,
		"sigma": sigma,
		"score": score,
		"mmr_score": {player: RL_BASE_MMR + RL_MMR_SCALE * score[player] for player in players},
		"strength": strengths,
		"ranking_triples": ranking_triples,
		"pairwise": direct,
		"pairwise_weights": {p: dict(raw_wins[p]) for p in players},
		"pairwise_probability_matrix": probability_matrix,
		"victory_matrix": {
			"players": players,
			"values": [
				[raw_wins[player].get(opponent, 0.0) if player != opponent else 0.0
				 for opponent in players]
				for player in players
			],
		},
	}


def _compat_entry(match, result, previous_result=None):
	"""Convert one V2 result into the existing Rocket League table schema.

	Args:
		match: Current normalized match dictionary.
		result: Ranking result returned by ``calculate_ranking``.
		previous_result: Optional result used to calculate per-player deltas.

	Returns:
		A dictionary containing RL-compatible MMR, matrix, probability and V2 data.
	"""
	mmr = {p: RL_BASE_MMR + RL_MMR_SCALE * result["score"][p] for p in result["players"]}
	matrix = [[0.0 for _ in result["players"]] for _ in result["players"]]
	indices = {p: i for i, p in enumerate(result["players"])}
	for player, row in indices.items():
		matrix[row][row] = mmr[player]
		for opponent, column in indices.items():
			if player != opponent:
				matrix[row][column] = mmr[opponent] - mmr[player]
	prev_mmr = previous_result and {
		p: RL_BASE_MMR + RL_MMR_SCALE * previous_result["score"][p]
		for p in previous_result["players"]
	}
	pre_match_strengths = {player: 1.0 for player in match["team_A"] + match["team_B"]}
	if previous_result is not None:
		pre_match_strengths.update({
			player: previous_result["strength"].get(player, 1.0)
			for player in pre_match_strengths
		})
	probability_a = _team_strength(match["team_A"], pre_match_strengths)
	probability_b = _team_strength(match["team_B"], pre_match_strengths)
	probability_a /= probability_a + probability_b
	probability_b = 1.0 - probability_a
	return {
		"Date": format_date(pd.to_datetime(match["timestamp"])),
		"Match": match.get("match_id"),
		"Blue Team": match["team_A"], "Orange Team": match["team_B"],
		"Blue Score": match["goal_A"], "Orange Score": match["goal_B"], "Overtime": match["overtime"],
		"Blue Win Prob.": round(probability_a, 2), "Orange Win Prob.": round(probability_b, 2),
		"Matrix Blue Prob.": probability_a, "Matrix Orange Prob.": probability_b,
		"Uncertainty Factors": result["sigma"],
		"Strength": result["strength"],
		"Total Delta": round_dict_values({p: mmr[p] - (prev_mmr or {}).get(p, RL_BASE_MMR) for p in mmr}),
		"Total MMR": round_dict_values(mmr), "Matrix MMR": matrix, "Matrix Indices": indices,
		"Ranking": result["ranking"], "Pairwise": result["pairwise"],
		"Ranking Triples": result["ranking_triples"],
		"Victory Matrix": result["victory_matrix"],
		"Victory Probability Matrix": result["pairwise_probability_matrix"],
	}


def get_RL_table(sheet_name):
	"""Read an RL sheet and recalculate V2 after every chronological match.

	Args:
		sheet_name: Google Sheet worksheet name read by ``read_sheet_df``.

	Returns:
		A list of RL-compatible snapshots, one for each active match.
	"""
	matches = []
	for _, row in read_sheet_df(sheet_name).iterrows():
		team_a = [p for p in row[RL_BLUE_TEAM_COLS] if pd.notna(p)]
		team_b = [p for p in row[RL_ORANGE_TEAM_COLS] if pd.notna(p)]
		if any(player in RL_DEACTIVATED_PLAYERS for player in team_a + team_b):
			continue
		matches.append({
			"match_id": int(row[RL_MATCH_COL]), "timestamp": pd.to_datetime(row[RL_DATE_COL]),
			"team_A": team_a, "team_B": team_b,
			"goal_A": _number(row[RL_BLUE_SCORE_COL]), "goal_B": _number(row[RL_ORANGE_SCORE_COL]),
			"overtime": convert_bool(row[RL_OVERTIME_COL]),
		})
	table = []
	previous = None
	players = []
	raw_wins = {}
	for match in [match for _, match in _ordered_matches(matches)]:
		match = {
			**match,
			"team_A": list(dict.fromkeys(match["team_A"])),
			"team_B": list(dict.fromkeys(match["team_B"])),
			"overtime_factor": 0.5,
			"margin_cap": 6.0,
		}
		_update_pairwise_state(match, players, raw_wins, discount_base=0.98)
		players = sorted(players)
		result = calculate_ranking(
			[],
			_raw_pairwise=raw_wins,
			_raw_players=players,
			_initial_strengths=previous.get("strength") if previous else None,
		)
		table.append(_compat_entry(match, result, previous))
		previous = result
	return table
