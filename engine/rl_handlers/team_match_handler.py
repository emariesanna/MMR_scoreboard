"""Team match handler for RL engine.

Calculates match outcome deltas based on team MMRs and match result.
"""
from ..rl_pipeline import RLHandler
from ..rl_context import RLContext


class RLTeamMatchHandler(RLHandler):
    """
    Calculates MMR deltas from match outcome.
    
    Responsibilities:
    - Calculate win probabilities based on team MMRs
    - Calculate match deltas based on actual outcome vs expected
    - Handle team size differences with k_factor
    - Apply overtime penalty (0.5x delta)
    
    Requires: 
        - context.blue_team, orange_team
        - context.blue_score, orange_score
        - context.overtime
        - context.players_mmr_at_day_start
    
    Modifies:
        - context.match_deltas (initializes base deltas)
        - context.blue_win_probability
        - context.orange_win_probability
    """
    
    def process(self, context: RLContext) -> RLContext:
        """Calculate match outcome deltas."""
        # Calculate win probabilities
        self._calculate_win_probability(context)
        
        # Determine winner
        blue_won = context.blue_score > context.orange_score
        
        # Calculate base delta
        blue_base_delta = (
            context.config.BASE_MMR_DELTA * 
            (blue_won - context.blue_win_probability) * 2  # Full delta at 50% win prob
        )
        
        # Apply overtime penalty
        if context.overtime:
            blue_base_delta *= 0.5
        
        # Adjust for team sizes
        blue_size = len(context.blue_team)
        orange_size = len(context.orange_team)
        
        blue_match_delta = blue_base_delta * orange_size / blue_size
        orange_match_delta = -blue_base_delta * blue_size / orange_size
        
        # Apply deltas to match_deltas
        for player in context.blue_team:
            context.match_deltas[player] += blue_match_delta
        
        for player in context.orange_team:
            context.match_deltas[player] += orange_match_delta
        
        return context
    
    def _calculate_win_probability(self, context: RLContext) -> None:
        """Calculate and store win probabilities for both teams."""
        blue_size = len(context.blue_team)
        orange_size = len(context.orange_team)
        
        # Calculate effective team MMRs with k_factor adjustment
        mmr_blue = (
            sum(context.players_mmr_at_day_start[p] for p in context.blue_team) * 
            blue_size ** (context.config.K_FACTOR - 1)
        )
        mmr_orange = (
            sum(context.players_mmr_at_day_start[p] for p in context.orange_team) * 
            orange_size ** (context.config.K_FACTOR - 1)
        )
        
        # Calculate win probability using logistic function
        mmr_diff = (mmr_orange - mmr_blue) / ((blue_size + orange_size) / 2)
        context.blue_win_probability = 1 / (1 + 10 ** (mmr_diff / context.config.GAMMA))
        context.orange_win_probability = 1 - context.blue_win_probability
