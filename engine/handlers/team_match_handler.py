"""Team match handler for MMR calculation engines."""
from abc import ABC, abstractmethod
from typing import Any, Dict, List


class TeamMatchHandler(ABC):
    """Handles team-based match outcome and MMR deltas."""
    
    def __init__(self, last_mmr: Dict[str, float], last_date_mmr: Dict[str, float],
                 base_mmr_delta: float, gamma: float):
        # Shared state references
        self.last_mmr = last_mmr
        self.last_date_mmr = last_date_mmr
        
        # Hyperparameters
        self.base_mmr_delta = base_mmr_delta
        self.gamma = gamma

    def calculate_win_probability(self, mmr_diff: float) -> tuple[float, float]:
        """Calculate win probabilities for both teams with team size scaling."""
        win_prob_a = 1 / (1 + 10 ** (mmr_diff / self.gamma))
        win_prob_b = 1 - win_prob_a

        return win_prob_a, win_prob_b
    
    @abstractmethod
    def calculate_mmr_diff(self, *args: Any) -> float:
        """Calculate MMR difference. Parameters depend on the specific game."""
        pass

    @abstractmethod
    def apply_match_outcome(self, *args: Any) -> Dict[str, float]:
        """Calculate and apply MMR deltas based on match outcome."""
        pass
    

class FifaTeamMatchHandler(TeamMatchHandler):
    """FIFA-specific team match handler with star ratings."""
    def __init__(self, last_mmr: Dict[str, float], last_date_mmr: Dict[str, float], base_mmr_delta: float, gamma: float, 
                    star_rating_factor: float):
        super().__init__(last_mmr, last_date_mmr, base_mmr_delta, gamma)
        # Hyperparameters
        self.star_rating_factor = star_rating_factor
    
    def calculate_mmr_diff(self, home_player: str, away_player: str,
                            stars_home: float, stars_away: float) -> float:
        home_base_mmr = self.last_date_mmr[home_player]
        away_base_mmr = self.last_date_mmr[away_player]
        
        star_factor = self.star_rating_factor * (stars_home - stars_away) / 2
        
        home_effective_mmr = home_base_mmr + star_factor
        away_effective_mmr = away_base_mmr - star_factor
        
        return away_effective_mmr - home_effective_mmr
    
    def apply_match_outcome(self, home_player: str, away_player: str, 
                           home_won: float, home_win_prob: float, penalties: bool) -> Dict[str, float]:
        """ Draw is represented with a home_won value of 0.5 """
        match_delta = {}

        match_delta[home_player] = self.base_mmr_delta * (home_won - home_win_prob) * 2 # Full delta at 50% win prob

        if penalties:
            match_delta[home_player] *= 0.5

        match_delta[away_player] = -match_delta[home_player]
        
        return match_delta
    

class RLTeamMatchHandler(TeamMatchHandler):
    """Rocket League-specific team match handler with no context factors."""
    def __init__(self, last_mmr: Dict[str, float], last_date_mmr: Dict[str, float], base_mmr_delta: float, gamma: float, 
                    k_factor: float):
        super().__init__(last_mmr, last_date_mmr, base_mmr_delta, gamma)
        # Hyperparameters
        self.k_factor = k_factor

    def calculate_mmr_diff(self, blue_team: List[str], orange_team: List[str]) -> float:
        size_a = len(blue_team)
        size_b = len(orange_team)
        
        mmr_a = sum(self.last_date_mmr[p] for p in blue_team) * size_a ** (self.k_factor - 1)
        mmr_b = sum(self.last_date_mmr[p] for p in orange_team) * size_b ** (self.k_factor - 1)
        
        return (mmr_b - mmr_a)/((size_a + size_b)/2)
    
    def apply_match_outcome(self, blue_team: List[str], orange_team: List[str], 
                           blue_won: int, blue_win_prob: float, overtime: bool) -> Dict[str, float]:
        match_delta = {}
        
        blue_size = len(blue_team)
        orange_size = len(orange_team)
        
        # Base delta calculation
        blue_base_delta = self.base_mmr_delta * (blue_won - blue_win_prob) * 2 # Full delta at 50% win prob
        
        # Reduce delta if overtime
        if overtime:
            blue_base_delta *= 0.5
        
        # Scale by opponent team size / own team size
        blue_delta = blue_base_delta * orange_size / blue_size
        orange_delta = -blue_base_delta * blue_size / orange_size
        
        # Apply to all players
        for player in blue_team:
            match_delta[player] = blue_delta
            self.last_mmr[player] += blue_delta
        
        for player in orange_team:
            match_delta[player] = orange_delta
            self.last_mmr[player] += orange_delta
        
        return match_delta

    

