"""Inactivity handler for MMR calculation engines."""
from abc import abstractmethod
from collections import defaultdict
from typing import Dict, Optional, List

class CoreDecayHandler:
    """Handles decay effects."""
    def __init__(self, decay_factor_per_day: float, mmr_reclaim: float):
        self.decay_factor_per_day = decay_factor_per_day
        self.mmr_reclaim = mmr_reclaim

        self.decay_adjustments = defaultdict(float)
        self.decay_adjustment_deltas = defaultdict(float)
        
    def get_decay_adjustment_deltas(self) -> Dict[str, float]:
        return self.decay_adjustment_deltas

    def process_decay(self, match_players: List[str],
                      inactivity_days: Dict[str, int], player_mmrs: Optional[Dict[str, float]]):
        if inactivity_days:

            for player, days in inactivity_days.items():
                decay_factor_increase = days * self.decay_factor_per_day
                self._calulate_decay_adjustment_deltas(player, decay_factor_increase, player_mmrs[player] if player_mmrs else None)

        for player in match_players:
            self.decay_adjustment_deltas[player] += min(
                self.mmr_reclaim, -self.decay_adjustments[player])

        self.decay_adjustments[player] += self.decay_adjustment_deltas[player]

    @abstractmethod
    def _calulate_decay_adjustment_deltas(self, player: str, decay_factor: float, player_mmr: Optional[float]):
        pass


class CappedDecayHandler(CoreDecayHandler):
    """Handles decay effects by reducing MMR by a percentage of a max decay value each day"""
    def __init__(self, decay_factor_per_day: float, mmr_reclaim: float, max_decay: float):
        super().__init__(decay_factor_per_day, mmr_reclaim)
        self.max_decay = max_decay

    def _calulate_decay_adjustment_deltas(self, player: str, decay_factor_increase: float):
        self.decay_adjustment_deltas[player] -= decay_factor_increase * self.max_decay
        self.decay_adjustment_deltas[player] = max(
            self.decay_adjustment_deltas[player], 
            self.decay_adjustments[player] - self.max_decay)


class UncappedDecayHandler(CoreDecayHandler):
    """Handles decay effects by reducing MMR by a percentage of player's MMR each day"""
    
    def _calulate_decay_adjustment_deltas(self, player: str, decay_factor_increase: float, player_mmr: Optional[float]):
        self.decay_adjustment_deltas[player] -= decay_factor_increase * player_mmr
        self.decay_adjustment_deltas[player] = max(
            self.decay_adjustment_deltas[player], 
            self.decay_adjustments[player] - player_mmr)
