"""Inactivity handler for MMR calculation engines."""
from abc import abstractmethod
from typing import Dict, List, Set

class CoreInactivityHandler:
    """Handles inactivity effects."""
    def __init__(self, 
                 active_players: Set[str], 
                 last_mmr: Dict[str, float], last_adjusted_mmr: Dict[str, float], total_delta: Dict[str, float],
                 inactivity_days: Dict[str, int],
                 total_inflation: List[float], decay_adjustments: Dict[str, float],
                 decay_factor_per_day: float, mmr_reclaim: float):
        # Shared state references
        self.active_players = active_players
        self.last_mmr = last_mmr
        self.total_inflation = total_inflation
        self.total_delta = total_delta
        self.inactivity_days = inactivity_days
        self.decay_adjustments = decay_adjustments
        self.last_adjusted_mmr = last_adjusted_mmr

        # Hyperparameters
        self.decay_factor_per_day = decay_factor_per_day
        self.mmr_reclaim = mmr_reclaim
    @abstractmethod
    def _increase_decay_adjustments(self, player: str, decay_factor: float):
        pass

    def apply_inactivity_effects(self, match_players: List[str]):
        for player in self.active_players:
            adjustment_delta = 0.0
            if self.inactivity_days[player]:
                decay_factor = min(self.inactivity_days[player] * self.decay_factor_per_day, 1)
                adjustment_delta = self._increase_decay_adjustments(player, decay_factor)
                self.inactivity_days[player] = 0
            if player in match_players:
                adjustment_delta += min(self.mmr_reclaim, - self.decay_adjustments[player])
            self.total_delta[player] += adjustment_delta
            self.total_inflation[0] += adjustment_delta
            self.decay_adjustments[player] += adjustment_delta
            self.last_adjusted_mmr[player] = self.last_mmr[player] + self.decay_adjustments[player]
            

class TsInactivityHandler(CoreInactivityHandler):
    """Handles inactivity effects like a TrueSkill system"""
    def __init__(self, 
                 active_players: Set[str], 
                 last_mmr: Dict[str, float], last_adjusted_mmr: Dict[str, float], total_delta: Dict[str, float],
                 total_inflation: List[float],
                 inactivity_days: Dict[str, int], decay_adjustments: Dict[str, float],
                 decay_factor_per_day: float, mmr_reclaim: float, max_decay: float):
        super().__init__(active_players, last_mmr, last_adjusted_mmr, total_delta, inactivity_days, total_inflation, decay_adjustments, decay_factor_per_day, mmr_reclaim)
        # Hyperparameters
        self.max_decay = max_decay

    def _increase_decay_adjustments(self, player: str, decay_factor: float):
            return - min(decay_factor * self.max_decay, self.last_mmr[player] + self.decay_adjustments[player])

    def apply_inactivity_effects(self, match_players: List[str]):
        super().apply_inactivity_effects(match_players)
        return
    
class ProportionalInactivityHandler(CoreInactivityHandler):
    """Handles inactivity effects by applying a proportional decay to the player's MMR."""
    def __init__(self, 
                 active_players: Set[str], 
                 last_mmr: Dict[str, float], last_date_mmr: Dict[str, float], last_adjusted_mmr: Dict[str, float], total_delta: Dict[str, float],
                 total_inflation: List[float],
                 inactivity_days: Dict[str, int], decay_adjustments: Dict[str, float],
                 decay_factor_per_day: float, mmr_reclaim: float):
        super().__init__(active_players, last_mmr, last_adjusted_mmr, total_delta, inactivity_days, total_inflation, decay_adjustments, decay_factor_per_day, mmr_reclaim)
        # Shared state references
        self.last_date_mmr = last_date_mmr
    
    def _increase_decay_adjustments(self, player: str, decay_factor: float):
        return - min(decay_factor * self.last_date_mmr[player], self.last_mmr[player] + self.decay_adjustments[player])
    
    def apply_inactivity_effects(self, match_players: List[str]):
        super().apply_inactivity_effects(match_players)
        return
