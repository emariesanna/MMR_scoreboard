"""Goal difference handler for MMR calculation engines."""
from typing import Dict, List


class GoalDifferenceHandler:
    """Handles goal difference bonus/penalty."""
    
    def __init__(self, last_mmr: Dict[str, float], goal_difference_factor: float):
        # Shared state references
        self.last_mmr = last_mmr
        
        # Hyperparameters
        self.goal_difference_factor = goal_difference_factor
    
    def apply_goal_difference(self, team_a: List[str], team_b: List[str],
                             score_a: int, score_b: int, match_deltas: Dict[str, float],
                             is_overtime: bool) -> Dict[str, float]:
        goal_diff_delta = {}
        
        if is_overtime or self.goal_difference_factor == 0:
            # No goal difference bonus in overtime
            return goal_diff_delta
        
        goal_diff_factor = (abs(score_a - score_b) / self.goal_difference_factor)
        
        for player in team_a:
            goal_diff_delta[player] = match_deltas[player] * goal_diff_factor
            self.last_mmr[player] += goal_diff_delta[player]
        
        for player in team_b:
            goal_diff_delta[player] = match_deltas[player] * goal_diff_factor
            self.last_mmr[player] += goal_diff_delta[player]
        
        return goal_diff_delta
