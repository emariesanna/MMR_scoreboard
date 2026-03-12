"""Uncertainty handler for MMR calculation engines."""
from typing import Dict, List
from datetime import datetime


class UncertaintyHandler:
    """Handles uncertainty amplification and reduction."""
    
    def __init__(self, 
                 active_players: List[str],
                 last_mmr: Dict[str, float], last_date_mmr: Dict[str, float], total_delta: Dict[str, float], 
                 uncertainty_factors: Dict[str, float], pre_match_uncertainty_factors: Dict[str, float], inactivity_days: Dict[str, int],
                 total_inflation: List[float], 
                 uncertainty_decay: float, uncertainty_increase: float, base_uncertainty: float):
        # Shared state references
        self.active_players = active_players
        self.uncertainty_factors = uncertainty_factors
        self.pre_match_uncertainty_factors = pre_match_uncertainty_factors
        self.last_mmr = last_mmr
        self.last_date_mmr = last_date_mmr
        self.total_inflation = total_inflation
        self.inactivity_days = inactivity_days
        self.total_delta = total_delta
        
        # Hyperparameters
        self.uncertainty_decay = uncertainty_decay
        self.uncertainty_increase = uncertainty_increase
        self.base_uncertainty = base_uncertainty

        # Internal state
        self.current_date = None
        self.last_date_uncertainties = {}  # Snapshot at beginning of day
    
    def _process_date_change(self, new_date: datetime):
        """
        Process date change for uncertainty amplification and reduction.
        Increases uncertainty based on days passed and reduces it based on decay.
        """
        if self.current_date == new_date:
            return 0

        if self.current_date is not None:
            days_passed = (new_date - self.current_date).days
            uncertainty_diff = self.uncertainty_increase * days_passed
            
            for p in self.active_players:
                new_uncertainty = self.uncertainty_factors[p] + uncertainty_diff
                
                if new_uncertainty < self.base_uncertainty:
                    self.uncertainty_factors[p] = round(new_uncertainty, 6)
                else:
                    self.inactivity_days[p] = int((new_uncertainty - self.base_uncertainty) / self.uncertainty_increase)
                    self.uncertainty_factors[p] = self.base_uncertainty
        
        self.last_date_mmr.update({p: self.last_mmr[p] for p in self.active_players})
        self.last_date_uncertainties = self.uncertainty_factors.copy()
        self.current_date = new_date

        return 
    
    def apply_uncertainty_amplification(self, players: List[str], new_date: datetime):
        """
        Apply uncertainty amplification to the total delta for the given players.
        Uses the snapshot of uncertainties at the start of the day for amplification.
        Also reduces uncertainty immediately after the match.
        """

        self._process_date_change(new_date)

        for player in self.active_players:
            self.pre_match_uncertainty_factors[player] = self.uncertainty_factors[player]

        for player in players:
            uncertainty_delta = self.total_delta[player] * (self.last_date_uncertainties[player] - 1)
            self.total_inflation[0] += uncertainty_delta
            self.total_delta[player] += uncertainty_delta
            self.last_mmr[player] += uncertainty_delta

            # Reduce uncertainty immediately after match
            self.uncertainty_factors[player] = round(
                max(1.0, self.uncertainty_factors[player] - self.uncertainty_decay), 6
            )
        
        return
