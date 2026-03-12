"""Context and configuration for Rocket League MMR engine."""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Set
from collections import defaultdict
from config import (
    RL_BASE_MMR, RL_GAMMA, RL_K_FACTOR, RL_BASE_MMR_DELTA, 
    RL_GOAL_DIFFERENCE_FACTOR, RL_BASE_UNCERTAINTY, 
    RL_UNCERTAINTY_DECAY, RL_UNCERTAINTY_INCREASE, 
    RL_MMR_DECAY_FACTOR_PER_DAY, RL_MMR_RECLAIM, RL_MAX_DECAY
)


@dataclass
class RLConfig:
    """Configuration/hyperparameters for RL MMR calculation."""
    BASE_MMR: float
    GAMMA: float
    K_FACTOR: float
    BASE_MMR_DELTA: float
    GOAL_DIFFERENCE_FACTOR: float
    BASE_UNCERTAINTY: float
    UNCERTAINTY_DECAY: float
    UNCERTAINTY_INCREASE: float
    MMR_DECAY_FACTOR_PER_DAY: float
    MMR_RECLAIM: float
    MAX_DECAY: float
    
    @classmethod
    def from_sheet_name(cls, sheet_name: str) -> 'RLConfig':
        """Create config from sheet name, loading sheet-specific parameters."""
        return cls(
            BASE_MMR=RL_BASE_MMR,
            GAMMA=RL_GAMMA,
            K_FACTOR=RL_K_FACTOR,
            BASE_MMR_DELTA=RL_BASE_MMR_DELTA,
            GOAL_DIFFERENCE_FACTOR=RL_GOAL_DIFFERENCE_FACTOR[sheet_name],
            BASE_UNCERTAINTY=RL_BASE_UNCERTAINTY,
            UNCERTAINTY_DECAY=RL_UNCERTAINTY_DECAY[sheet_name],
            UNCERTAINTY_INCREASE=RL_UNCERTAINTY_INCREASE,
            MMR_DECAY_FACTOR_PER_DAY=RL_MMR_DECAY_FACTOR_PER_DAY,
            MMR_RECLAIM=RL_MMR_RECLAIM,
            MAX_DECAY=RL_MAX_DECAY
        )


@dataclass
class RLContext:
    """
    Single source of truth for RL engine state.
    
    Separates match-scoped data (cleared each match) from session-scoped data
    (persists across matches).
    """
    # Match data (per-match scope)
    current_date: datetime = None
    match_number: int = 0
    blue_team: List[str] = field(default_factory=list)
    orange_team: List[str] = field(default_factory=list)
    blue_score: int = 0
    orange_score: int = 0
    overtime: bool = False
    
    # Player state (session scope)
    players_mmr: Dict[str, float] = field(default_factory=lambda: defaultdict(float))
    players_adjusted_mmr: Dict[str, float] = field(default_factory=lambda: defaultdict(float))
    players_mmr_at_day_start: Dict[str, float] = field(default_factory=lambda: defaultdict(float))
    
    # Match deltas (per-match scope, cleared each match)
    match_deltas: Dict[str, float] = field(default_factory=lambda: defaultdict(float))
    
    # Uncertainty tracking (session scope)
    uncertainty_factors: Dict[str, float] = field(default_factory=lambda: defaultdict(float))
    uncertainty_at_day_start: Dict[str, float] = field(default_factory=lambda: defaultdict(float))
    uncertainty_snapshot: Dict[str, float] = field(default_factory=lambda: defaultdict(float))
    
    # Inactivity tracking (session scope)
    inactivity_days: Dict[str, int] = field(default_factory=lambda: defaultdict(int))
    decay_adjustments: Dict[str, float] = field(default_factory=lambda: defaultdict(float))
    
    # Inflation tracking (session scope)
    session_inflation: float = 0.0
    inflation_factor: float = 1.0
    
    # Active players (session scope)
    active_players: Set[str] = field(default_factory=set)
    
    # Output data (per-match scope)
    blue_win_probability: float = 0.0
    orange_win_probability: float = 0.0
    
    # Config/hyperparameters
    config: RLConfig = None
    
    # Internal state for date tracking
    _last_processed_date: datetime = None
    _previous_inflation_factor: float = 1.0
    
    @classmethod
    def initialize(cls, config: RLConfig) -> 'RLContext':
        """Initialize a new context with config and default values."""
        context = cls(config=config)
        
        # Initialize defaultdicts with base values
        context.players_mmr = defaultdict(lambda: config.BASE_MMR)
        context.players_adjusted_mmr = defaultdict(lambda: config.BASE_MMR)
        context.players_mmr_at_day_start = defaultdict(lambda: config.BASE_MMR)
        context.uncertainty_factors = defaultdict(lambda: config.BASE_UNCERTAINTY)
        context.uncertainty_at_day_start = defaultdict(lambda: config.BASE_UNCERTAINTY)
        context.uncertainty_snapshot = defaultdict(lambda: config.BASE_UNCERTAINTY)
        
        return context
    
    def load_match(self, match_row) -> None:
        """Load match data from pandas row into context."""
        import pandas as pd
        from utils import format_date, convert_bool
        from config import (
            RL_DATE_COL, RL_MATCH_COL, RL_BLUE_TEAM_COLS, RL_ORANGE_TEAM_COLS,
            RL_BLUE_SCORE_COL, RL_ORANGE_SCORE_COL, RL_OVERTIME_COL
        )
        
        _, row = match_row
        
        self.current_date = pd.to_datetime(row[RL_DATE_COL])
        self.match_number = int(row[RL_MATCH_COL])
        self.blue_team = [p for p in row[RL_BLUE_TEAM_COLS] if pd.notna(p)]
        self.orange_team = [p for p in row[RL_ORANGE_TEAM_COLS] if pd.notna(p)]
        self.blue_score = row[RL_BLUE_SCORE_COL]
        self.orange_score = row[RL_ORANGE_SCORE_COL]
        self.overtime = convert_bool(row[RL_OVERTIME_COL])
        
        # Update active players
        self.active_players.update(self.blue_team + self.orange_team)
    
    def to_table_row(self) -> dict:
        """Convert current context state to table row format."""
        from utils import format_date, round_dict_values
        
        return {
            "Date": format_date(self.current_date),
            "Match": self.match_number,
            "Blue Team": self.blue_team,
            "Orange Team": self.orange_team,
            "Blue Score": self.blue_score,
            "Orange Score": self.orange_score,
            "Overtime": self.overtime,
            "Blue Win Prob.": round(self.blue_win_probability, 2),
            "Orange Win Prob.": round(self.orange_win_probability, 2),
            "Uncertainty Factors": self.uncertainty_snapshot.copy(),
            "Total Delta": round_dict_values(self.match_deltas.copy()),
            "Total MMR": round_dict_values(self.players_adjusted_mmr.copy()),
            "Inflation Factor": round(self.inflation_factor, 2)
        }
    
    def reset_match_scope(self) -> None:
        """Reset match-scoped data. Called by pipeline before processing."""
        self.match_deltas = defaultdict(float)
        self.blue_win_probability = 0.0
        self.orange_win_probability = 0.0
