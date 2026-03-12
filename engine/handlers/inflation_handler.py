"""Inflation handler for MMR calculation engines."""
from typing import Dict, List, Set

class InflationHandler:
    """Handles inflation correction by applying a factor to all active players."""
    def __init__(self, active_players: Set[str], total_inflation: List[float], inflation_factor: List[float], total_delta: Dict[str, float], last_adjusted_mmr: Dict[str, float], base_mmr: int):
        # Shared state references
        self.active_players = active_players
        self.total_inflation = total_inflation
        self.inflation_factor = inflation_factor
        self.total_delta = total_delta
        self.last_adjusted_mmr = last_adjusted_mmr

        # Hyperparameters
        self.base_mmr = base_mmr

        # Internal state
        self.previous_inflation_factor = 1.0
    
    def apply_inflation_correction(self):
        """
        Apply a simple inflation factor to all active players.
        Uses total_inflation to calculate the factor, then applies it multiplicatively.
        """
        
        # Calculate inflation factor based on accumulated inflation
        self.inflation_factor[0] = 1.0 + self.total_inflation[0] / (len(self.active_players) * self.base_mmr)
        inflation_factor_diff = self.inflation_factor[0] - self.previous_inflation_factor
        self.previous_inflation_factor = self.inflation_factor[0]

        # Apply factor to all players
        for player in self.active_players:
            self.total_delta[player] -= self.last_adjusted_mmr[player] * inflation_factor_diff
            self.last_adjusted_mmr[player] -= self.last_adjusted_mmr[player] * inflation_factor_diff
        return


class EqualInflationHandler:
    """Handles inflation correction by distributing equally to all active players."""
    def __init__(self, active_players: Set[str], total_inflation: List[float], total_delta: Dict[str, float], last_adjusted_mmr: Dict[str, float], base_mmr: int):
        # Shared state references
        self.active_players = active_players
        self.total_inflation = total_inflation
        self.total_delta = total_delta
        self.last_adjusted_mmr = last_adjusted_mmr

        # Hyperparameters
        self.base_mmr = base_mmr

        # Internal state
        self.previous_inflation = 0.0
    
    def apply_inflation_correction(self):
        for player in self.active_players:
            self.total_delta[player] -= (self.total_inflation[0] - self.previous_inflation) / len(self.active_players)
            self.last_adjusted_mmr[player] -= (self.total_inflation[0] - self.previous_inflation) / len(self.active_players)
            self.previous_inflation = self.total_inflation[0]
        
        return

