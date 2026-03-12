"""Uncertainty handler for RL engine.

Amplifies deltas based on player uncertainty and reduces uncertainty after matches.
"""
from ..rl_pipeline import RLHandler
from ..rl_context import RLContext


class RLUncertaintyHandler(RLHandler):
    """
    Amplifies match deltas based on player uncertainty factors.
    
    Responsibilities:
    - Snapshot pre-match uncertainty for output
    - Amplify match deltas by uncertainty factor
    - Track inflation caused by uncertainty amplification
    - Reduce uncertainty for match participants
    
    Requires:
        - context.match_deltas (from TeamMatch + GoalDiff)
        - context.uncertainty_at_day_start
        - context.blue_team, orange_team
    
    Modifies:
        - context.match_deltas (amplification)
        - context.uncertainty_factors (reduction after match)
        - context.session_inflation (accumulates uncertainty inflation)
        - context.uncertainty_snapshot (for output)
    """
    
    def process(self, context: RLContext) -> RLContext:
        """Apply uncertainty amplification and reduction."""
        # Snapshot pre-match uncertainty for all active players (for output)
        for player in context.active_players:
            context.uncertainty_snapshot[player] = context.uncertainty_factors[player]
        
        # Amplify deltas for match participants based on uncertainty
        match_players = context.blue_team + context.orange_team
        
        for player in match_players:
            # Use day-start uncertainty for amplification
            uncertainty_at_start = context.uncertainty_at_day_start[player]
            
            # Calculate amplification (uncertainty - 1) * delta
            uncertainty_delta = context.match_deltas[player] * (uncertainty_at_start - 1)
            
            # Apply amplification
            context.match_deltas[player] += uncertainty_delta
            
            # Track inflation
            context.session_inflation += uncertainty_delta
            
            # Reduce uncertainty immediately after match
            new_uncertainty = max(
                1.0, 
                context.uncertainty_factors[player] - context.config.UNCERTAINTY_DECAY
            )
            context.uncertainty_factors[player] = round(new_uncertainty, 6)
        
        return context
