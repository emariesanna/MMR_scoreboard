"""Free-for-all match handler for racing/FFA game modes (e.g., Mario Kart)."""
from typing import Dict, List


class FreeForAllMatchHandler:
    """
    Handles free-for-all matches using pairwise Elo comparisons.
    
    Each player is compared against all others in the match:
    - Player finishing ahead "beats" all players behind them
    - Delta normalized by (n-1) to keep magnitude consistent across field sizes
    """
    
    def __init__(self, last_mmr: Dict[str, float], last_date_mmr: Dict[str, float],
                 base_mmr_delta: float, gamma: float):
        # Shared state references
        self.last_mmr = last_mmr
        self.last_date_mmr = last_date_mmr
        
        # Hyperparameters
        self.base_mmr_delta = base_mmr_delta
        self.gamma = gamma
    
    def apply_match_outcome(self, players_ordered: List[str]) -> Dict[str, float]:
        """
        Calculate and apply pairwise Elo deltas for all players in a free-for-all match.
        
        Args:
            players_ordered: List of player names in finishing order (1st to last)
        
        Returns:
            pairwise_delta dict mapping player names to their MMR deltas
        """
        pairwise_delta = {}
        n = len(players_ordered)
        
        if n < 2:
            return pairwise_delta
        
        # For each player, compare against all others
        for idx_i, player_i in enumerate(players_ordered):
            delta_i = 0.0
            
            for idx_j, player_j in enumerate(players_ordered):
                if idx_i == idx_j:
                    continue
                
                # Score: 1 if player_i finished ahead of player_j, else 0
                score_ij = 1.0 if idx_i < idx_j else 0.0
                
                # Expected probability that player_i beats player_j
                mmr_i = self.last_date_mmr[player_i]
                mmr_j = self.last_date_mmr[player_j]
                expected_ij = 1.0 / (1.0 + 10.0 ** ((mmr_j - mmr_i) / self.gamma))
                
                # Delta contribution from this comparison, normalized by (n-1)
                delta_i += self.base_mmr_delta * (score_ij - expected_ij) / (n - 1)
            
            pairwise_delta[player_i] = delta_i
            self.last_mmr[player_i] += delta_i
        
        return pairwise_delta
