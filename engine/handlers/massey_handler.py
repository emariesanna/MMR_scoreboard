import numpy as np
from collections import defaultdict
from typing import Dict, List, Tuple


class MasseyHandler:
    """
    Holistic rating system: solves a least-squares system over ALL matches every time
    a new match is added, so every game has equal weight and ratings are fully
    retroactive.  Team rating = average of member ratings, which handles variable
    compositions and unequal team sizes naturally.
    """

    def __init__(
        self,
        base_mmr: float,
        scale: float,
        gamma: float,
        goal_diff_factor: float,
        goal_diff_cap: int,
        regularization: float = 0.0,
        decay: float = 1.0,
        matchup_balance: float = 0.5,
    ):
        self.base_mmr = base_mmr
        self.scale = scale
        self.gamma = gamma
        self.goal_diff_factor = goal_diff_factor
        self.goal_diff_cap = goal_diff_cap
        # Adds regularization * I to the normal equations matrix.
        # Equivalent to each player having `regularization` phantom draws vs an average
        # opponent — dampens oscillations when few real games have been played.
        self.regularization = regularization
        # Per-match exponential decay: match k (of M total) gets weight decay^(M-1-k).
        # decay=1.0 means uniform weight (no forgetting). decay=0.98 → half-life ~35 matches.
        self.decay = decay
        # Saturation exponent for repeated matchups.
        # Total weight of a matchup played n times scales as D^matchup_balance, where D is
        # the sum of decay weights for that matchup.  Within a matchup, recency (decay)
        # still determines the distribution of that total weight.
        #   1.0 = no saturation (current behaviour, n repeats count n× more than 1 game)
        #   0.5 = sqrt saturation (20 repeats ≈ 4.5× a single game — recommended default)
        #   0.0 = full balance (every distinct matchup always contributes 1 unit)
        self.matchup_balance = matchup_balance
        # (blue_team, orange_team, effective_diff)
        self._matches: List[Tuple[List[str], List[str], float]] = []
        self._ratings: Dict[str, float] = {}

    def effective_goal_diff(
        self, blue_score: int, orange_score: int, overtime: bool
    ) -> float:
        diff = blue_score - orange_score
        sign = 1.0 if diff > 0 else -1.0
        abs_diff = min(abs(diff), self.goal_diff_cap)
        weight = 1.0 + (abs_diff - 1) / self.goal_diff_factor
        if overtime:
            weight *= 0.5
        return sign * weight

    def predict_win_prob(
        self, blue_team: List[str], orange_team: List[str]
    ) -> Tuple[float, float]:
        if not self._ratings:
            return 0.5, 0.5
        avg_blue = (
            sum(self._ratings.get(p, self.base_mmr) for p in blue_team) / len(blue_team)
        )
        avg_orange = (
            sum(self._ratings.get(p, self.base_mmr) for p in orange_team)
            / len(orange_team)
        )
        prob_blue = 1.0 / (1.0 + 10.0 ** ((avg_orange - avg_blue) / self.gamma))
        return prob_blue, 1.0 - prob_blue

    def add_match_and_recompute(
        self,
        blue_team: List[str],
        orange_team: List[str],
        blue_score: int,
        orange_score: int,
        overtime: bool,
    ):
        eff = self.effective_goal_diff(blue_score, orange_score, overtime)
        self._matches.append((blue_team, orange_team, eff))
        self._recompute()

    def _recompute(self):
        # Collect players in order of first appearance
        seen: Dict[str, int] = {}
        for blue, orange, _ in self._matches:
            for p in blue + orange:
                if p not in seen:
                    seen[p] = len(seen)

        N = len(seen)
        if N == 0:
            self._ratings = {}
            return

        M = len(self._matches)
        X = np.zeros((M, N))
        d = np.zeros(M)

        for k, (blue, orange, eff) in enumerate(self._matches):
            for p in blue:
                X[k, seen[p]] += 1.0 / len(blue)
            for p in orange:
                X[k, seen[p]] -= 1.0 / len(orange)
            d[k] = eff

        # Base decay weights: match k gets decay^(M-1-k); most recent = 1.
        decay_w = (
            self.decay ** np.arange(M - 1, -1, -1)
            if self.decay < 1.0
            else np.ones(M)
        )

        # Matchup saturation: group repeated identical matchups and scale their combined
        # weight as D^alpha where D = sum of decay weights in that matchup group.
        #   alpha=1.0 → no saturation   alpha=0.5 → √n   alpha=0.0 → each matchup = 1 unit
        if self.matchup_balance < 1.0:
            matchup_count: Dict[frozenset, int] = defaultdict(int)
            matchup_decay_sum: Dict[frozenset, float] = defaultdict(float)
            keys = []
            for k, (blue, orange, _) in enumerate(self._matches):
                key = frozenset({frozenset(blue), frozenset(orange)})
                keys.append(key)
                matchup_count[key] += 1
                matchup_decay_sum[key] += decay_w[k]

            # Total weight per matchup = n^alpha (count-based, timing-independent).
            # Within a matchup the weight is distributed proportionally to decay_w,
            # so recent games still matter more — but the matchup's total contribution
            # is never reduced just because its games were played earlier in the season.
            alpha = self.matchup_balance
            combined_w = np.array([
                decay_w[k] * (matchup_count[keys[k]] ** alpha) / matchup_decay_sum[keys[k]]
                for k in range(M)
            ])
        else:
            combined_w = decay_w

        XW = X * combined_w[:, np.newaxis]

        # Weighted normal equations: X^T W X r = X^T W d
        A = XW.T @ X
        b = XW.T @ d

        # Regularization (phantom draws): pulls ratings toward the mean.
        # Applied before the constraint row so it affects all N players.
        if self.regularization > 0.0:
            A += self.regularization * np.eye(N)

        # sum(r) = 0 constraint (replaces last row)
        A[-1, :] = 1.0
        b[-1] = 0.0

        try:
            r = np.linalg.solve(A, b)
        except np.linalg.LinAlgError:
            r, *_ = np.linalg.lstsq(A, b, rcond=None)

        self._ratings = {
            p: float(self.base_mmr + r[i] * self.scale) for p, i in seen.items()
        }

    def get_ratings(self) -> Dict[str, float]:
        return self._ratings.copy()

    def build_matrix(self) -> Tuple[List[List[float]], Dict[str, int]]:
        """
        Returns (matrix, player_indices) in the same format as RLMatrixHandler:
          - diagonal:     player's Massey MMR
          - off-diagonal: matrix[row][col] = mmr[col] - mmr[row]
                          (positive = column player is stronger than row player)
        """
        if not self._ratings:
            return [], {}

        players = list(self._ratings.keys())
        player_indices = {p: i for i, p in enumerate(players)}
        N = len(players)

        matrix = [[0.0] * N for _ in range(N)]
        for p_row, i in player_indices.items():
            for p_col, j in player_indices.items():
                if i == j:
                    matrix[i][j] = self._ratings[p_row]
                else:
                    matrix[i][j] = self._ratings[p_col] - self._ratings[p_row]

        return matrix, player_indices
