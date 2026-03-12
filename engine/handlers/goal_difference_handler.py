"""Goal difference handler for MMR calculation engines."""
from abc import abstractmethod
from typing import Any, Dict, List, Optional


class GoalDifferenceHandler:
    """Handles goal difference bonus/penalty."""
    
    def __init__(self, last_mmr: Dict[str, float], total_delta: Dict[str, float], 
                 goal_difference_factor: float):
        # Shared state references
        self.last_mmr = last_mmr
        self.total_delta = total_delta
        
        # Hyperparameters
        self.goal_difference_factor = goal_difference_factor

    @abstractmethod
    def apply_goal_difference(self, team_a: Any, team_b: Any, score: List[int], is_overtime: Optional[bool]):
        pass

class RLGoalDifferenceHandler(GoalDifferenceHandler):
    """Rocket League-specific goal difference handler with overtime handling."""
    
    def apply_goal_difference(self, blue_team: List[str], orange_team: List[str], score: List[int], is_overtime: bool):
        if is_overtime:
            return
        
        blue_score, orange_score = score

        goal_diff_factor = (abs(blue_score - orange_score) / self.goal_difference_factor)
        
        for p in blue_team:
            goal_difference_delta = self.total_delta[p] * goal_diff_factor
            self.total_delta[p] += goal_difference_delta
            self.last_mmr[p] += goal_difference_delta
        
        for p in orange_team:
            goal_difference_delta = self.total_delta[p] * goal_diff_factor
            self.total_delta[p] += goal_difference_delta
            self.last_mmr[p] += goal_difference_delta
        
        return
    

class FifaGoalDifferenceHandler(GoalDifferenceHandler):
    """FIFA-specific goal difference handler without overtime handling."""
    
    def apply_goal_difference(self, home_player: str, away_player: str, score: List[int]):
        home_score, away_score, home_penalties_score, away_penalties_score = score

        if home_penalties_score > 0 or away_penalties_score > 0:
            return
        
        goal_diff_factor = (abs(home_score - away_score) / self.goal_difference_factor)
        
        goal_difference_delta = self.total_delta[home_player] * goal_diff_factor
        self.total_delta[home_player] += goal_difference_delta
        self.last_mmr[home_player] += goal_difference_delta
    
        goal_difference_delta = self.total_delta[away_player] * goal_diff_factor
        self.total_delta[away_player] += goal_difference_delta
        self.last_mmr[away_player] += goal_difference_delta
        
        return
