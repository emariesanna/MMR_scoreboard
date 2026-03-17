"""Inflation handler for MMR calculation engines."""
from collections import defaultdict
import logging
from typing import Dict, Set

class InflationHandler:
    """Handles inflation correction by applying a factor to all active players."""
    def __init__(self, base_mmr: int, logger_name: str = "rl_engine_handlers"):
        self.base_mmr = base_mmr
        self.logger = logging.getLogger(logger_name)

        self.total_inflation = 0.0
        self.last_inflation_adjustments = defaultdict(float)
        self.inflation_adjustment_deltas = defaultdict(float)

    def get_inflation_adjustment_deltas(self) -> Dict[str, float]:
        return self.inflation_adjustment_deltas
    
    def process_inflation(
        self, inflation_deltas: Dict[str, float], active_players: Set[str], player_mmrs: Dict[str, float]):
        
        self.total_inflation += sum(inflation_deltas.values())
        raw_mmr_sum = sum(player_mmrs[p] - self.last_inflation_adjustments[p] for p in active_players)
        inflation_factor = self.total_inflation / raw_mmr_sum

        for player in active_players:
            new_adjustment = -1 * ((player_mmrs[player] - self.last_inflation_adjustments[player]) * inflation_factor)
            self.inflation_adjustment_deltas[player] = new_adjustment - self.last_inflation_adjustments[player]
            self.last_inflation_adjustments[player] = new_adjustment
        self.logger.info(
            "INFLATION_HANDLER | inflation factor=%f | inflation_adjustment_deltas=%s",
            inflation_factor,
            {k: round(v, 3) for k, v in sorted(self.inflation_adjustment_deltas.items())},
        )
        return

