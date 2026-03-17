"""Goal difference handler for MMR calculation engines."""
from abc import abstractmethod
import logging
from typing import Any, Dict, List


class GoalDifferenceHandler:
    """Handles goal difference bonus/penalty."""
    
    def __init__(self, base_mmr_delta: float, goal_difference_factor: float, logger_name: str = "rl_engine_handlers"):
        self.base_mmr_delta = base_mmr_delta
        self.goal_difference_factor = goal_difference_factor
        self.logger = logging.getLogger(logger_name)

        self.goal_deltas = {}

    def get_goal_deltas(self) -> Dict[str, float]:
        return self.goal_deltas

    @abstractmethod
    def process_goal_difference(self, *args: Any):
        pass

    def _calculate_goal_deltas(self, players: List[str], a_score: int, b_score: int, base_deltas: Dict[str, float]):
        goal_diff_factor = (abs(a_score - b_score) / self.goal_difference_factor)
        
        for player in players:
            self.goal_deltas[player] = max(min(base_deltas.get(player, 0) * goal_diff_factor, self.base_mmr_delta), -self.base_mmr_delta)


class RLGoalDifferenceHandler(GoalDifferenceHandler):
    """Goal difference handler with overtime handling."""
    
    def process_goal_difference(self, 
                                blue_team: List[str], orange_team: List[str],
                                blue_score: int, orange_score: int, overtime: bool,
                                base_deltas: Dict[str, float]):
        self.goal_deltas.clear()

        if overtime:
            self.logger.info("GOAL_DIFFERENCE_HANDLER | overtime=True | goal_deltas={}")
            return
        
        self._calculate_goal_deltas(
            blue_team + orange_team, blue_score, orange_score, base_deltas)
        self.logger.info(
            "GOAL_DIFFERENCE_HANDLER | goal_deltas=%s",
            {k: round(v, 3) for k, v in sorted(self.goal_deltas.items())},
        )
        
        return
    

class FifaGoalDifferenceHandler(GoalDifferenceHandler):
    """Goal difference handler with penalties handling."""
    
    def process_goal_difference(self, 
                                home_player: str, away_player: str, 
                                home_score: int, away_score: int,
                                home_penalties_score: int, away_penalties_score: int,
                                base_deltas: Dict[str, float]):
        
        self.goal_deltas.clear()

        if home_penalties_score > 0 or away_penalties_score > 0:
            return
        
        self._calculate_goal_deltas(
            [home_player, away_player], home_score, away_score, base_deltas)
        
        return