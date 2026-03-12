# RL Engine v2 - Pipeline Architecture

## Overview

Refactored Rocket League MMR engine with modular pipeline architecture. This replaces the original `engine_rl.py` implementation which used 12+ shared variables and list[0] hacks.

## Key Improvements

### Before (engine_rl.py)
```python
# 12+ shared state variables
active_players = set()
blue_win_prob = [0.0]  # list[0] hack for mutability
orange_win_prob = [0.0]
last_mmr = defaultdict(lambda: RL_BASE_MMR)
last_date_mmr = defaultdict(lambda: RL_BASE_MMR)
last_adjusted_mmr = defaultdict(lambda: RL_BASE_MMR)
total_delta = defaultdict(float)
uncertainty_factors = defaultdict(lambda: RL_BASE_UNCERTAINTY)
pre_match_uncertainty_factors = defaultdict(lambda: RL_BASE_UNCERTAINTY)
inactivity_days = defaultdict(int)
decay_adjustments = defaultdict(float)
total_inflation = [0.0]
inflation_factor = [1.0]

# Manual handler instantiation with many parameters
team_match = RLTeamMatchHandler(blue_win_prob, orange_win_prob, 
                                last_mmr, last_date_mmr, total_delta, 
                                RL_BASE_MMR_DELTA, RL_GAMMA, RL_K_FACTOR)
# ... repeat for each handler

# Manual state clearing
total_delta.clear()

# Manual handler calls
team_match.apply_match_outcome(blue_team, orange_team, [blue_score, orange_score], overtime)
goal_diff.apply_goal_difference(blue_team, orange_team, [blue_score, orange_score], overtime)
uncertainty.apply_uncertainty_amplification(blue_team + orange_team, date_val)
inactivity.apply_inactivity_effects(blue_team + orange_team)
inflation.apply_inflation_correction()
```

### After (engine_rl_v2.py)
```python
# Single context object
config = RLConfig.from_sheet_name(sheet_name)
context = RLContext.initialize(config)

# Clean pipeline definition
pipeline = RLPipeline([
    RLDateChangeHandler(),
    RLTeamMatchHandler(),
    RLGoalDifferenceHandler(),
    RLUncertaintyHandler(),
    RLInactivityHandler(),
    RLInflationHandler(),
])

# Simple processing loop
for match_data in read_sheet_df(sheet_name).iterrows():
    context.load_match(match_data)
    context = pipeline.process_match(context)  # Auto-resets match deltas
    table.append(context.to_table_row())
```

## Architecture

### Core Components

#### 1. RLContext (`rl_context.py`)
Single source of truth containing all engine state:
- **Match-scoped data**: Reset each match (match_deltas, current scores, win probabilities)
- **Session-scoped data**: Persists across matches (players_mmr, uncertainty_factors, active_players)
- **Config**: Hyperparameters loaded from config.py

#### 2. RLPipeline (`rl_pipeline.py`)
Orchestrates handler execution:
- Automatically resets match-scoped data
- Chains handlers sequentially
- Applies accumulated deltas to MMR after handlers

#### 3. RLHandler (`rl_pipeline.py`)
Abstract base for all handlers:
```python
class RLHandler(ABC):
    def process(self, context: RLContext) -> RLContext:
        pass
```

### Handler Chain (Order Matters!)

1. **RLDateChangeHandler** - Detects date changes, updates uncertainty/inactivity
2. **RLTeamMatchHandler** - Calculates match outcome deltas
3. **RLGoalDifferenceHandler** - Amplifies deltas by goal difference
4. **RLUncertaintyHandler** - Amplifies by uncertainty, reduces uncertainty
5. **RLInactivityHandler** - Applies decay/reclaim
6. **RLInflationHandler** - Distributes inflation correction

Each handler:
- Is **independent** and **testable** in isolation
- Has **clear responsibilities** documented in docstring
- **Modifies only context** (no external side effects)
- **Returns context** for chain clarity

## Files

```
engine/
├── rl_context.py           # RLContext + RLConfig dataclasses
├── rl_pipeline.py          # RLHandler abstract + RLPipeline
├── engine_rl_v2.py         # New pipeline-based engine
└── rl_handlers/            # Modular handlers
    ├── __init__.py
    ├── date_change_handler.py
    ├── team_match_handler.py
    ├── goal_difference_handler.py
    ├── uncertainty_handler.py
    ├── inactivity_handler.py
    └── inflation_handler.py
```

## Testing

Run comparison test:
```bash
# Test specific sheet
python test_rl_refactor.py "3v3"

# Test all sheets
python test_rl_refactor.py
```

The test compares V1 (original) vs V2 (pipeline) outputs match-by-match:
- MMR values (tolerance: 0.01)
- Win probabilities
- Uncertainty factors
- Inflation factors
- All other fields (exact match)

## Benefits

### ✅ Modularity
- Each handler is a self-contained module
- Easy to add/remove/reorder handlers
- Clear dependencies documented

### ✅ Testability
- Handlers can be unit tested with mock contexts
- No need to recreate 12+ variables for testing
- Integration tests compare full pipeline output

### ✅ Maintainability
- No list[0] hacks or reference tricks
- Clear separation of concerns
- Consistent interface across handlers

### ✅ Extensibility
- Creating new engines = config + handler chain
- Reuse handlers across different game modes
- Easy to experiment with handler variants

## Migration Path

1. ✅ **Phase 1**: Create foundation (RLContext, RLPipeline)
2. ✅ **Phase 2**: Create handler wrappers
3. ✅ **Phase 3**: Create engine_rl_v2.py
4. ⏳ **Phase 4**: Run comparison tests
5. ⏳ **Phase 5**: Replace engine_rl.py after validation

## Future Work

- [ ] Apply same pattern to FIFA/MK engines
- [ ] Add handler conditional execution (e.g., `should_process()` method)
- [ ] Add pipeline validation (check handler order dependencies)
- [ ] Unit tests for individual handlers
- [ ] Performance profiling per handler

## Notes

- Output format is **identical** to original engine
- Performance should be similar or better (less overhead)
- All original handler logic preserved (wrappers, not rewrites)
