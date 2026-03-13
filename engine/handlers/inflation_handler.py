"""Inflation handler for MMR calculation engines."""
from collections import defaultdict
from typing import Dict, Set

class InflationHandler:
    """Handles inflation correction by applying a factor to all active players."""
    def __init__(self, base_mmr: int):
        self.base_mmr = base_mmr

        self.inflation_adjustment_deltas = defaultdict(float)

    def get_inflation_adjustment_deltas(self) -> Dict[str, float]:
        return self.inflation_adjustment_deltas
    
    def process_inflation(
        self, inflation_deltas: Dict[str, float], active_players: Set[str], player_mmrs: Dict[str, float]):

        inflation_factor_delta = sum(inflation_deltas.values()) / (len(active_players) * self.base_mmr)

        for player in active_players:
            self.inflation_adjustment_deltas[player] = (player_mmrs[player] * inflation_factor_delta)
        return

