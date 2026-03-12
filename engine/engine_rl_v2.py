"""Rocket League MMR calculation engine - Pipeline Architecture (v2).

This is a refactored version of engine_rl.py using modular pipeline architecture.
Key improvements:
- Single RLContext object instead of 12+ shared variables
- No list[0] hacks for mutability
- Handlers are independent and testable
- Clear separation of match-scoped vs session-scoped data
- Pipeline automatically resets match deltas
"""
from gsheets import read_sheet_df
from .rl_context import RLContext, RLConfig
from .rl_pipeline import RLPipeline
from .rl_handlers import (
    RLDateChangeHandler,
    RLTeamMatchHandler,
    RLGoalDifferenceHandler,
    RLUncertaintyHandler,
    RLInactivityHandler,
    RLInflationHandler,
)


def get_RL_table(sheet_name):
    """
    Calculate RL MMR table using pipeline architecture.
    
    Table structure (same as original):
    {
      "Date": str,
      "Match": int,
      "Blue Team": [str],
      "Orange Team": [str],
      "Blue Score": int,
      "Orange Score": int,
      "Overtime": bool,
      "Blue Win Prob.": float,
      "Orange Win Prob.": float,
      "Uncertainty Factors": {str: float},
      "Total Delta": {str: int},
      "Total MMR": {str: int},
      "Inflation Factor": float
    }
    
    Args:
        sheet_name: Name of the Google Sheets sheet to read data from
        
    Returns:
        List of match result rows
    """
    table = []
    
    # 1. Load configuration
    config = RLConfig.from_sheet_name(sheet_name)
    
    # 2. Define pipeline (order is critical!)
    pipeline = RLPipeline([
        RLDateChangeHandler(),      # Must be first - updates day snapshots
        RLTeamMatchHandler(),        # Calculates base match deltas
        RLGoalDifferenceHandler(),   # Amplifies deltas by goal difference
        RLUncertaintyHandler(),      # Amplifies by uncertainty, reduces uncertainty
        RLInactivityHandler(),       # Applies decay/reclaim
        RLInflationHandler(),        # Distributes inflation correction
    ])
    
    # 3. Initialize context with config
    context = RLContext.initialize(config)
    
    # 4. Process matches through pipeline
    for match_data in read_sheet_df(sheet_name).iterrows():
        # Load match data into context
        context.load_match(match_data)
        
        # Process through pipeline (automatically resets match_deltas)
        context = pipeline.process_match(context)
        
        # Append formatted row to table
        table.append(context.to_table_row())
    
    return table
