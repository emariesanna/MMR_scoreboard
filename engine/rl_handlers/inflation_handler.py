"""Inflation handler for RL engine.

Distributes accumulated inflation correction across all active players.
"""
from ..rl_pipeline import RLHandler
from ..rl_context import RLContext


class RLInflationHandler(RLHandler):
    """
    Applies inflation correction using multiplicative factor approach.
    
    Responsibilities:
    - Calculate inflation factor from accumulated session inflation
    - Apply inflation correction to all active players
    - Track factor changes to avoid double-correction
    
    Requires:
        - context.session_inflation (accumulated from uncertainty/inactivity)
        - context.active_players
        - context.players_adjusted_mmr
    
    Modifies:
        - context.match_deltas (adds inflation correction)
        - context.inflation_factor (updates multiplicative factor)
        - context._previous_inflation_factor (internal tracking)
    """
    
    def process(self, context: RLContext) -> RLContext:
        """Apply inflation correction."""
        # Calculate new inflation factor
        num_players = len(context.active_players)
        
        if num_players == 0:
            return context
        
        # Multiplicative approach: factor = 1 + (total_inflation / (num_players * base_mmr))
        context.inflation_factor = 1.0 + (
            context.session_inflation / 
            (num_players * context.config.BASE_MMR)
        )
        
        # Calculate incremental change in factor
        inflation_factor_diff = context.inflation_factor - context._previous_inflation_factor
        
        # Apply correction to all active players
        for player in context.active_players:
            current_adjusted_mmr = (
                context.players_mmr[player] + context.decay_adjustments[player]
            )
            
            # Correction is proportional to current MMR and factor change
            correction = -current_adjusted_mmr * inflation_factor_diff
            
            context.match_deltas[player] += correction
        
        # Update internal tracking
        context._previous_inflation_factor = context.inflation_factor
        
        return context
