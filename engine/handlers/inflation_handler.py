"""Inflation handler for MMR calculation engines."""
from typing import Dict, Set


class InflationHandler:
    """Handles inflation correction to keep total MMR constant."""
    
    def __init__(self, active_players: Set[str], last_mmr: Dict[str, float]):
        # Shared state references
        self.active_players = active_players
        self.last_mmr = last_mmr
    
    def apply_inflation_correction(self, total_inflation: float) -> Dict[str, float]:
        """
        Distribute inflation proportionally to all active players.
        Returns inflation_delta dict.
        """
        inflation_delta = {}
        
        if not self.active_players or total_inflation == 0:
            return inflation_delta
        
        total_mmr = sum(self.last_mmr[p] for p in self.active_players)
        
        for player in self.active_players:
            inflation_delta[player] = -total_inflation * (self.last_mmr[player] / total_mmr)
            self.last_mmr[player] += inflation_delta[player]
        
        return inflation_delta


class EqualInflationHandler:
    """Handles inflation correction by distributing equally to all active players."""
    
    def __init__(self, active_players: Set[str], last_mmr: Dict[str, float]):
        # Shared state references
        self.active_players = active_players
        self.last_mmr = last_mmr
    
    def apply_inflation_correction(self, total_inflation: float) -> Dict[str, float]:
        """
        Distribute inflation equally to all active players.
        Returns inflation_delta dict.
        """
        inflation_delta = {}
        
        if not self.active_players or total_inflation == 0:
            return inflation_delta
        
        # Equal distribution
        equal_share = -total_inflation / len(self.active_players)
        
        for player in self.active_players:
            inflation_delta[player] = equal_share
            self.last_mmr[player] += inflation_delta[player]
        
        return inflation_delta
