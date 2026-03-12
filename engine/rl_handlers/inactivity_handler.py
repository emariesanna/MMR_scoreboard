"""Inactivity handler for RL engine.

Applies MMR decay for inactive players and reclaim for returning players.
"""
from ..rl_pipeline import RLHandler
from ..rl_context import RLContext


class RLInactivityHandler(RLHandler):
    """
    Handles inactivity decay and reclaim (TrueSkill-style).
    
    Responsibilities:
    - Apply decay to players who have accumulated inactivity days
    - Apply reclaim bonus to match participants with negative decay adjustments
    - Track decay adjustments separately from main MMR
    - Contribute to session inflation
    
    Requires:
        - context.inactivity_days
        - context.decay_adjustments
        - context.active_players
        - context.blue_team, orange_team
    
    Modifies:
        - context.match_deltas (adds decay/reclaim adjustments)
        - context.decay_adjustments (tracks cumulative decay)
        - context.inactivity_days (resets to 0 after decay applied)
        - context.session_inflation (accumulates decay/reclaim)
    """
    
    def process(self, context: RLContext) -> RLContext:
        """Apply inactivity effects."""
        match_players = context.blue_team + context.orange_team
        
        for player in context.active_players:
            adjustment_delta = 0.0
            
            # Apply decay if player has inactivity days
            if context.inactivity_days[player] > 0:
                decay_factor = min(
                    context.inactivity_days[player] * context.config.MMR_DECAY_FACTOR_PER_DAY,
                    1.0
                )
                
                # Calculate decay (TrueSkill style - capped by max_decay)
                current_mmr = context.players_mmr[player] + context.decay_adjustments[player]
                decay_amount = min(
                    decay_factor * context.config.MAX_DECAY,
                    current_mmr
                )
                
                adjustment_delta -= decay_amount
                context.inactivity_days[player] = 0
            
            # Apply reclaim if player is in match and has negative decay
            if player in match_players and context.decay_adjustments[player] < 0:
                reclaim_amount = min(
                    context.config.MMR_RECLAIM,
                    -context.decay_adjustments[player]
                )
                adjustment_delta += reclaim_amount
            
            # Apply adjustment
            if adjustment_delta != 0:
                context.match_deltas[player] += adjustment_delta
                context.session_inflation += adjustment_delta
                context.decay_adjustments[player] += adjustment_delta
        
        return context
