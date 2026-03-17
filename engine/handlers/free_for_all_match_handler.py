"""Free-for-all match handler for racing/FFA game modes (e.g., Mario Kart)."""
from collections import defaultdict
from datetime import datetime
import logging
from typing import DefaultDict, Dict, List


class FreeForAllMatchHandler:
    """
    Handles free-for-all matches using pairwise Elo comparisons.
    
    Each player is compared against all others in the match:
    - Player finishing ahead "beats" all players behind them
    - Delta normalized by (n-1) to keep magnitude consistent across field sizes
    """
    
    def __init__(self, base_mmr_delta: float, gamma: float, logger_name: str = "rl_engine_handlers"):
        self.base_mmr_delta = base_mmr_delta
        self.gamma = gamma
        self.logger = logging.getLogger(logger_name)
        
        self.last_date = None
        self.last_date_mmrs = defaultdict(float)
        self.match_deltas = {}
    
    def get_match_deltas(self) -> Dict[str, float]:
        return self.match_deltas
    
    def process_match_outcome(self, 
                              date_val: datetime,
                              players_ordered: List[str],
                              player_mmrs: DefaultDict[str, float]) -> Dict[str, float]:
        """
        Calculate pairwise Elo deltas for all players in a free-for-all match.
        
        Args:
            date_val: Current date
            players_ordered: List of player names in finishing order (1st to last)
            player_mmrs: Current MMR dictionary for all players
        
        Returns:
            pairwise_delta dict mapping player names to their MMR deltas
        """
        if self.last_date is None or date_val > self.last_date:
            self.last_date = date_val
            self.last_date_mmrs = player_mmrs.copy()
        
        self.match_deltas = {}
        n = len(players_ordered)
        
        if n < 2:
            self.logger.info("FREE_FOR_ALL_MATCH_HANDLER | match_deltas={}")
            return self.match_deltas
        
        # For each player, compare against all others
        for idx_i, player_i in enumerate(players_ordered):
            delta_i = 0.0
            
            for idx_j, player_j in enumerate(players_ordered):
                if idx_i == idx_j:
                    continue
                
                # Score: 1 if player_i finished ahead of player_j, else 0
                score_ij = 1.0 if idx_i < idx_j else 0.0
                
                # Expected probability that player_i beats player_j
                mmr_i = self.last_date_mmrs[player_i]
                mmr_j = self.last_date_mmrs[player_j]
                expected_ij = 1.0 / (1.0 + 10.0 ** ((mmr_j - mmr_i) / self.gamma))
                
                # Delta contribution from this comparison, normalized by (n-1)
                delta_i += self.base_mmr_delta * (score_ij - expected_ij) * 2 / (n - 1)  # Full delta at 50% win prob
            
            self.match_deltas[player_i] = delta_i
        
        self.logger.info(
            "FREE_FOR_ALL_MATCH_HANDLER | match_deltas=%s",
            {k: round(v, 3) for k, v in sorted(self.match_deltas.items())},
        )
        
        return self.match_deltas
