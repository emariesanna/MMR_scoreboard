"""Presentation helpers for the Bradley-Terry Rocket League engine V2."""

import pandas as pd

from config import RL_HIDDEN_PLAYERS


def prepare_ranking_intervals(table):
    """Prepare the latest conservative ranking interval for charting.

    Args:
        table: Match snapshots returned by ``engine.engineV2.get_RL_table``.

    Returns:
        A DataFrame with one row per visible player and columns for the
        lower bound, conservative score, and upper bound of the ranking
        triple ``theta - 3sigma``, ``theta - k*sigma``, ``theta + 3sigma``.
    """
    if not table:
        return pd.DataFrame(columns=["Player", "Lower", "Score", "Upper"])

    rows = []
    for item in table[-1].get("Ranking Triples", []):
        if item["player"] in RL_HIDDEN_PLAYERS:
            continue
        rows.append({
            "Player": item["player"],
            "Lower": item.get("mmr_minus_3sigma", item["theta_minus_3sigma"]),
            "Score": item.get("mmr_score", item["theta_minus_k_sigma"]),
            "Upper": item.get("mmr_plus_3sigma", item["theta_plus_3sigma"]),
        })

    return pd.DataFrame(rows).sort_values("Score", ascending=False).reset_index(drop=True)


def prepare_victory_matrix(table):
    """Prepare the latest relative pairwise win matrix for charting.

    Args:
        table: Match snapshots returned by ``engine.engineV2.get_RL_table``.

    Returns:
        A square DataFrame whose rows are winners and columns are defeated
        players. Values are direct weighted win probabilities in ``[0, 1]``;
        they include goal-margin, overtime and pairwise temporal discount
        factors, without Laplace smoothing. Missing matchups are ``NaN``.
    """
    if not table:
        return pd.DataFrame()

    matrix = table[-1].get("Victory Probability Matrix")
    if matrix is None:
        raw_matrix = table[-1].get("Victory Matrix", {})
        raw_players = raw_matrix.get("players", [])
        raw_values = raw_matrix.get("values", [])
        raw_indices = {player: index for index, player in enumerate(raw_players)}
        probability_values = []
        for player in raw_players:
            row = []
            for opponent in raw_players:
                if player == opponent:
                    row.append(None)
                    continue
                forward = raw_values[raw_indices[player]][raw_indices[opponent]]
                reverse = raw_values[raw_indices[opponent]][raw_indices[player]]
                total = forward + reverse
                row.append(forward / total if total else None)
            probability_values.append(row)
        matrix = {"players": raw_players, "values": probability_values}
    ranking_order = [
        item["player"]
        for item in sorted(
            table[-1].get("Ranking Triples", []),
            key=lambda item: item.get("theta_minus_k_sigma", float("-inf")),
            reverse=True,
        )
        if item["player"] not in RL_HIDDEN_PLAYERS
    ]
    players = [p for p in ranking_order if p in matrix.get("players", [])]
    players.extend(
        p for p in matrix.get("players", [])
        if p not in players and p not in RL_HIDDEN_PLAYERS
    )
    values = matrix.get("values", [])
    indices = {player: index for index, player in enumerate(matrix.get("players", []))}
    result = pd.DataFrame(
        [
            [
                values[indices[row]][indices[column]]
                if values[indices[row]][indices[column]] is not None else float("nan")
                for column in players
            ]
            for row in players
        ],
        index=players,
        columns=players,
        dtype=float,
    )
    raw_matrix = table[-1].get("Victory Matrix", {})
    raw_players = raw_matrix.get("players", [])
    raw_values = raw_matrix.get("values", [])
    raw_indices = {player: index for index, player in enumerate(raw_players)}
    for player in players:
        if player not in raw_indices:
            continue
        row_index = raw_indices[player]
        wins = 0.0
        encounters = 0.0
        for opponent in raw_players:
            if opponent == player or opponent not in raw_indices:
                continue
            opponent_index = raw_indices[opponent]
            wins += raw_values[row_index][opponent_index]
            encounters += raw_values[row_index][opponent_index] + raw_values[opponent_index][row_index]
        result.loc[player, player] = wins / encounters if encounters else float("nan")
    return result


def prepare_model_probability_matrix(table):
    """Prepare pairwise win probabilities implied by the fitted model.

    Args:
        table: Match snapshots returned by ``engine.engineV2.get_RL_table``.

    Returns:
        A square DataFrame where each cell is the Bradley-Terry probability
        that the row player defeats the column player. Unlike
        ``prepare_victory_matrix``, this matrix uses fitted strengths rather
        than only direct weighted encounters.
    """
    if not table:
        return pd.DataFrame()

    entry = table[-1]
    strengths = entry.get("Strength", entry.get("strength", {}))
    players = [
        item["player"]
        for item in sorted(
            entry.get("Ranking Triples", []),
            key=lambda item: item.get("theta_minus_k_sigma", float("-inf")),
            reverse=True,
        )
        if item["player"] not in RL_HIDDEN_PLAYERS
    ]
    players.extend(
        player for player in strengths
        if player not in players and player not in RL_HIDDEN_PLAYERS
    )
    result = pd.DataFrame(
        [
            [
                float("nan") if player == opponent else strengths[player] / (strengths[player] + strengths[opponent])
                for opponent in players
            ]
            for player in players
        ],
        index=players,
        columns=players,
        dtype=float,
    )
    raw_matrix = entry.get("Victory Matrix", {})
    raw_players = raw_matrix.get("players", [])
    raw_values = raw_matrix.get("values", [])
    raw_indices = {player: index for index, player in enumerate(raw_players)}
    for player in players:
        weighted_probability = 0.0
        total_volume = 0.0
        for opponent in players:
            if opponent == player:
                continue
            probability = result.loc[player, opponent]
            if pd.isna(probability):
                continue
            if player in raw_indices and opponent in raw_indices:
                player_index = raw_indices[player]
                opponent_index = raw_indices[opponent]
                volume = raw_values[player_index][opponent_index] + raw_values[opponent_index][player_index]
            else:
                volume = 1.0
            weighted_probability += probability * volume
            total_volume += volume
        result.loc[player, player] = (
            weighted_probability / total_volume if total_volume else float("nan")
        )
    return result
