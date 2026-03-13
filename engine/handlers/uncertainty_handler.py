"""Uncertainty handler for MMR calculation engines."""
from collections import defaultdict
from typing import Dict


class UncertaintyHandler:
    """Handles uncertainty amplification and reduction."""
    
    def __init__(self, uncertainty_decay: float, uncertainty_increase: float, 
                 base_uncertainty: float):
        self.uncertainty_decay = uncertainty_decay
        self.uncertainty_increase = uncertainty_increase
        self.base_uncertainty = base_uncertainty

        self.uncertainty_deltas = {}
        self.last_date_uncertainty_factors = defaultdict(lambda: base_uncertainty)
        self.inactivity_days = {}

        self.uncertainty_factors = defaultdict(lambda: base_uncertainty)

    def get_last_date_uncertainty_factors(self) -> Dict[str, float]:
        return self.last_date_uncertainty_factors
    
    def get_uncertainty_deltas(self) -> Dict[str, float]:
        return self.uncertainty_deltas

    def get_inactivity_days(self) -> Dict[str, int]:
        return self.inactivity_days
    
    def process_uncertainty(self, base_deltas: Dict[str, float], inactivity_days: Dict[str, int]):

        if inactivity_days:

            for player, days in inactivity_days.items():
                uncertainty_diff = self.uncertainty_increase * days
                new_uncertainty = self.uncertainty_factors[player] + uncertainty_diff
                if new_uncertainty < self.base_uncertainty:
                    self.uncertainty_factors[player] = round(new_uncertainty, 6)
                else:
                    inactivity_days[player] = int((new_uncertainty - self.base_uncertainty) / self.uncertainty_increase)
                    self.uncertainty_factors[player] = self.base_uncertainty

            self.last_date_uncertainty_factors.update(self.uncertainty_factors)

        self.inactivity_days = inactivity_days

        for player, delta in base_deltas.items():
            self.uncertainty_deltas[player] = delta * (self.last_date_uncertainty_factors[player] - 1)

            self.uncertainty_factors[player] = round(
                max(1.0, self.uncertainty_factors[player] - self.uncertainty_decay), 6
            )
        
        return
