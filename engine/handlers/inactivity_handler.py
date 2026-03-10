"""Inactivity handler for MMR calculation engines."""
from typing import Dict, Set
from datetime import datetime


class InactivityHandler:
    """Handles inactivity effects: uncertainty increase and MMR decay."""
    
    def __init__(self, active_players: Set[str], last_mmr: Dict[str, float], 
                 uncertainty_factors: Dict[str, float], last_date_mmr: Dict[str, float],
                 uncertainty_increase: float, mmr_decay_per_day: float, base_uncertainty: float):
        # Shared state references
        self.active_players = active_players
        self.last_mmr = last_mmr
        self.uncertainty_factors = uncertainty_factors
        self.last_date_mmr = last_date_mmr
        
        # Hyperparameters
        self.uncertainty_increase = uncertainty_increase
        self.mmr_decay_per_day = mmr_decay_per_day
        self.base_uncertainty = base_uncertainty
        
        # Internal state
        self.last_date = None
    
    def process_date_change(self, current_date: datetime) -> Dict[str, float]:
        """
        Process inactivity effects when date changes.
        Returns decay_delta dict for inactive players.
        """
        decay_delta = {}
        
        if self.last_date is None:
            self.last_date = current_date
            return decay_delta
        
        if self.last_date == current_date:
            return decay_delta
        
        # Update last_date_mmr snapshot
        self.last_date_mmr.clear()
        self.last_date_mmr.update(self.last_mmr)
        
        # Calculate uncertainty increase and decay
        days_passed = (current_date - self.last_date).days
        uncertainty_diff = self.uncertainty_increase * days_passed
        
        for player in self.active_players:
            new_uncertainty = self.uncertainty_factors[player] + uncertainty_diff
            
            if new_uncertainty < self.base_uncertainty:
                # No decay, just increase uncertainty
                self.uncertainty_factors[player] = round(new_uncertainty, 6)
            else:
                # Apply decay for exceeded uncertainty
                excess_uncertainty = new_uncertainty - self.base_uncertainty
                decay_delta[player] = -(excess_uncertainty / self.uncertainty_increase * 
                                       self.mmr_decay_per_day * self.last_date_mmr[player])
                self.last_mmr[player] += decay_delta[player]
                self.uncertainty_factors[player] = self.base_uncertainty
        
        self.last_date = current_date
        return decay_delta
