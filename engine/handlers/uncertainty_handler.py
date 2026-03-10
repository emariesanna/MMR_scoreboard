"""Uncertainty handler for MMR calculation engines."""
from typing import Dict, List


class UncertaintyHandler:
    """Handles uncertainty amplification and reduction."""
    
    def __init__(self, last_mmr: Dict[str, float], uncertainty_factors: Dict[str, float],
                 uncertainty_decay: float):
        # Shared state references
        self.last_mmr = last_mmr
        self.uncertainty_factors = uncertainty_factors
        
        # Hyperparameters
        self.uncertainty_decay = uncertainty_decay
    
    def apply_uncertainty_amplification(self, players: List[str], base_deltas: Dict[str, float]) -> Dict[str, float]:
        """
        Amplify deltas based on uncertainty factors and reduce uncertainty.
        Returns uncertainty_delta dict.
        """
        uncertainty_delta = {}
        
        for player in players:
            # Amplification: delta * (uncertainty - 1)
            uncertainty_delta[player] = base_deltas[player] * (self.uncertainty_factors[player] - 1)
            self.last_mmr[player] += uncertainty_delta[player]
            
            # Reduce uncertainty after match
            self.uncertainty_factors[player] = round(
                max(1.0, self.uncertainty_factors[player] - self.uncertainty_decay), 6
            )
        
        return uncertainty_delta
