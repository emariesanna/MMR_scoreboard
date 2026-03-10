"""Uncertainty handler for MMR calculation engines."""
from typing import Dict, List
from datetime import datetime


class UncertaintyHandler:
    """Handles uncertainty amplification and reduction."""
    
    def __init__(self, last_mmr: Dict[str, float], uncertainty_factors: Dict[str, float],
                 uncertainty_decay: float):
        # Shared state references
        self.last_mmr = last_mmr
        self.uncertainty_factors = uncertainty_factors
        
        # Hyperparameters
        self.uncertainty_decay = uncertainty_decay
        
        # Snapshot management for fairness (same uncertainty for all matches in a day)
        self.last_date_uncertainties = {}  # Snapshot at beginning of day
        self.current_date = None
    
    def process_date_change(self, new_date: datetime):
        """
        Process date change: create snapshot of current uncertainties.
        Should be called before processing matches of a new date.
        """
        if self.current_date is None or self.current_date != new_date:
            # Save snapshot for new day
            self.last_date_uncertainties = self.uncertainty_factors.copy()
            self.current_date = new_date
    
    def apply_uncertainty_amplification(self, players: List[str], base_deltas: Dict[str, float]) -> Dict[str, float]:
        """
        Amplify deltas based on beginning-of-day uncertainty and reduce uncertainty immediately.
        Uses last_date_uncertainties snapshot for amplification (fairness).
        Updates uncertainty_factors immediately after each match.
        Returns uncertainty_delta dict.
        """
        uncertainty_delta = {}
        
        for player in players:
            # Use snapshot for amplification (or current if no snapshot yet)
            snapshot_uncertainty = self.last_date_uncertainties.get(player, self.uncertainty_factors[player])
            uncertainty_delta[player] = base_deltas[player] * (snapshot_uncertainty - 1)
            self.last_mmr[player] += uncertainty_delta[player]
            
            # Reduce uncertainty immediately after match
            self.uncertainty_factors[player] = round(
                max(1.0, self.uncertainty_factors[player] - self.uncertainty_decay), 6
            )
        
        return uncertainty_delta
