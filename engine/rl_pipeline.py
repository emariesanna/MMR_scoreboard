"""Pipeline architecture for RL MMR engine handlers."""
from abc import ABC, abstractmethod
from typing import List
from collections import defaultdict
from .rl_context import RLContext


class RLHandler(ABC):
    """
    Abstract base class for all RL handlers.
    
    Each handler processes a context and returns the modified context.
    Handlers should be stateless except for configuration - all state lives in context.
    """
    
    @abstractmethod
    def process(self, context: RLContext) -> RLContext:
        """
        Process the context and return the modified version.
        
        Args:
            context: Current engine context with all state
            
        Returns:
            Modified context (can be same object, returned for chain clarity)
        """
        pass


class RLPipeline:
    """
    Pipeline that chains multiple handlers sequentially.
    
    Automatically resets match-scoped data before processing each match.
    """
    
    def __init__(self, handlers: List[RLHandler]):
        """
        Initialize pipeline with handlers.
        
        Args:
            handlers: List of handlers to execute in order. Order matters!
                     Typical order: DateChange → TeamMatch → GoalDiff → 
                                   Uncertainty → Inactivity → Inflation
        """
        self.handlers = handlers
    
    def process_match(self, context: RLContext) -> RLContext:
        """
        Process a single match through the handler pipeline.
        
        Automatically resets match-scoped data (match_deltas) before processing.
        
        Args:
            context: Context with loaded match data
            
        Returns:
            Context after processing through all handlers
        """
        # Reset match-scoped data
        context.reset_match_scope()
        
        # Execute pipeline
        for handler in self.handlers:
            context = handler.process(context)
        
        # Apply accumulated deltas to MMR
        for player in context.active_players:
            context.players_mmr[player] += context.match_deltas[player]
            context.players_adjusted_mmr[player] = (
                context.players_mmr[player] + context.decay_adjustments[player]
            )
        
        return context
