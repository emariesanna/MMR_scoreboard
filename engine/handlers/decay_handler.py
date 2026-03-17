"""Inactivity handler for MMR calculation engines."""
from abc import abstractmethod
from collections import defaultdict
import logging
from typing import Dict, List

class CoreDecayHandler:
    """Handles decay effects."""
    def __init__(self, decay_factor_per_day: float, mmr_reclaim: float, 
                 logger_name: str = "rl_engine_handlers"):
        self.decay_factor_per_day = decay_factor_per_day
        self.mmr_reclaim = mmr_reclaim
        self.logger = logging.getLogger(logger_name)

        self.decay_adjustments = defaultdict(float)
        self.decay_adjustment_deltas = defaultdict(float)
        
    def get_decay_adjustment_deltas(self) -> Dict[str, float]:
        return self.decay_adjustment_deltas

    def process_decay(self, match_players: List[str],
                      inactivity_days: Dict[str, int], player_mmrs: Dict[str, float]):
        
        self.decay_adjustment_deltas.clear()

        if inactivity_days:

            for player, days in inactivity_days.items():
                decay_factor_increase = days * self.decay_factor_per_day
                self._calculate_decay_adjustment_deltas(player, decay_factor_increase, player_mmrs[player])

            for player in match_players:
                self.decay_adjustment_deltas[player] += min(
                    self.mmr_reclaim, -self.decay_adjustments[player])

            for player in self.decay_adjustment_deltas:
                self.decay_adjustments[player] += self.decay_adjustment_deltas[player]
        
        self.logger.info(
            "DECAY_HANDLER | decay_adjustment_deltas=%s",
            {k: round(v, 3) for k, v in sorted(self.decay_adjustment_deltas.items())},
        )

    @abstractmethod
    def _calculate_decay_adjustment_deltas(self, player: str, decay_factor: float, player_mmr: float):
        pass


class CappedDecayHandler(CoreDecayHandler):
    """Handles decay effects by reducing MMR by a percentage of a max decay value each day"""
    def __init__(self, decay_factor_per_day: float, mmr_reclaim: float, max_decay: float,
                 logger_name: str = "rl_engine_handlers"):
        super().__init__(decay_factor_per_day, mmr_reclaim, logger_name)
        self.max_decay = max_decay

    def _calculate_decay_adjustment_deltas(self, player: str, decay_factor_increase: float, player_mmr: float):
        self.decay_adjustment_deltas[player] -= decay_factor_increase * self.max_decay
        self.decay_adjustment_deltas[player] = max(
            self.decay_adjustment_deltas[player], 
            self.decay_adjustments[player] - self.max_decay,
            - player_mmr)


class UncappedDecayHandler(CoreDecayHandler):
    """Handles decay effects by reducing MMR by a percentage of player's MMR each day"""
    
    def _calculate_decay_adjustment_deltas(self, player: str, decay_factor_increase: float, player_mmr: float):
        self.decay_adjustment_deltas[player] -= decay_factor_increase * player_mmr
        self.decay_adjustment_deltas[player] = max(
            self.decay_adjustment_deltas[player], 
            self.decay_adjustments[player] - player_mmr)
