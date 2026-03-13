"""Goal difference handler for MMR calculation engines."""
from abc import abstractmethod
from typing import Any, Dict, List


class GoalDifferenceHandler:
    """Handles goal difference bonus/penalty."""
    
    def __init__(self, goal_difference_factor: float):
        self.goal_difference_factor = goal_difference_factor

        self.goal_deltas = {}

    def get_goal_deltas(self) -> Dict[str, float]:
        return self.goal_deltas

    @abstractmethod
    def process_goal_difference(self, *args: Any):
        pass

    def _calculate_goal_deltas(self, players: List[str], a_score: int, b_score: int, base_deltas: Dict[str, float]):
        goal_diff_factor = (abs(a_score - b_score) / self.goal_difference_factor)
        
        for player in players:
            self.goal_deltas[player] = base_deltas.get(player, 0) * goal_diff_factor


class RLGoalDifferenceHandler(GoalDifferenceHandler):
    """Goal difference handler with overtime handling."""
    
    def process_goal_difference(self, 
                                blue_team: List[str], orange_team: List[str],
                                blue_score: int, orange_score: int, overtime: bool,
                                base_deltas: Dict[str, float]):
        if overtime:
            self.goal_deltas.clear()
            return

        self._calculate_goal_deltas(
            blue_team + orange_team, blue_score, orange_score, base_deltas)
        
        return
    

class FifaGoalDifferenceHandler(GoalDifferenceHandler):
    """Goal difference handler with penalties handling."""
    
    def process_goal_difference(self, 
                                home_player: str, away_player: str, 
                                home_score: int, away_score: int,
                                home_penalties_score: int, away_penalties_score: int,
                                base_deltas: Dict[str, float]):

        if home_penalties_score > 0 or away_penalties_score > 0:
            return
        
        self._calculate_goal_deltas(
            [home_player, away_player], home_score, away_score, base_deltas)
        
        return
