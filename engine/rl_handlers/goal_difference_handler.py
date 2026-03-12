"""Goal difference handler for RL engine.

Amplifies match deltas based on goal difference.
"""
from ..rl_pipeline import RLHandler
from ..rl_context import RLContext


class RLGoalDifferenceHandler(RLHandler):
    """
    Amplifies match deltas based on goal difference.
    
    Responsibilities:
    - Calculate goal difference factor
    - Amplify existing match deltas proportionally
    - Skip amplification if match went to overtime
    
    Requires:
        - context.match_deltas (populated by TeamMatchHandler)
        - context.blue_score, orange_score
        - context.overtime
        - context.blue_team, orange_team
    
    Modifies:
        - context.match_deltas (amplification)
    """
    
    def process(self, context: RLContext) -> RLContext:
        """Amplify deltas based on goal difference."""
        # Skip if overtime (overtime goals don't count for bonus)
        if context.overtime:
            return context
        
        # Calculate goal difference factor
        goal_diff = abs(context.blue_score - context.orange_score)
        goal_diff_factor = goal_diff / context.config.GOAL_DIFFERENCE_FACTOR
        
        # Amplify deltas for all match players
        all_players = context.blue_team + context.orange_team
        
        for player in all_players:
            goal_difference_delta = context.match_deltas[player] * goal_diff_factor
            context.match_deltas[player] += goal_difference_delta
        
        return context
