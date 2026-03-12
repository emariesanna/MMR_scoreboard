"""Date change handler for RL engine.

Extracted from UncertaintyHandler to make it a separate, composable module.
"""
from ..rl_pipeline import RLHandler
from ..rl_context import RLContext


class RLDateChangeHandler(RLHandler):
    """
    Handles date transitions between matches.
    
    Responsibilities:
    - Detect date changes
    - Update uncertainty factors based on days passed
    - Move overflow uncertainty to inactivity_days
    - Update day-start snapshots for MMR and uncertainty
    
    Requires: context.current_date
    Modifies: 
        - context.uncertainty_factors
        - context.inactivity_days
        - context.players_mmr_at_day_start
        - context.uncertainty_at_day_start
        - context._last_processed_date
    """
    
    def process(self, context: RLContext) -> RLContext:
        """Process date change if needed."""
        # Skip if same date as last processed
        if context._last_processed_date == context.current_date:
            return context
        
        # If this is the first match, just set snapshots
        if context._last_processed_date is None:
            self._update_snapshots(context)
            context._last_processed_date = context.current_date
            return context
        
        # Calculate days passed
        days_passed = (context.current_date - context._last_processed_date).days
        
        if days_passed > 0:
            # Increase uncertainty for all active players
            uncertainty_increase = context.config.UNCERTAINTY_INCREASE * days_passed
            
            for player in context.active_players:
                new_uncertainty = context.uncertainty_factors[player] + uncertainty_increase
                
                # If uncertainty exceeds base, convert excess to inactivity days
                if new_uncertainty >= context.config.BASE_UNCERTAINTY:
                    excess = new_uncertainty - context.config.BASE_UNCERTAINTY
                    context.inactivity_days[player] = int(
                        excess / context.config.UNCERTAINTY_INCREASE
                    )
                    context.uncertainty_factors[player] = context.config.BASE_UNCERTAINTY
                else:
                    context.uncertainty_factors[player] = round(new_uncertainty, 6)
        
        # Update snapshots for new day
        self._update_snapshots(context)
        context._last_processed_date = context.current_date
        
        return context
    
    def _update_snapshots(self, context: RLContext) -> None:
        """Update day-start snapshots."""
        context.players_mmr_at_day_start.update({
            p: context.players_mmr[p] for p in context.active_players
        })
        context.uncertainty_at_day_start = context.uncertainty_factors.copy()
