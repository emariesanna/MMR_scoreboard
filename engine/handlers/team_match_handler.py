"""Team match handler for MMR calculation engines."""
from abc import ABC, abstractmethod
from typing import Any, Dict, List


class TeamMatchHandler(ABC):
    """Calculates MMR delta from match outcome, updating total delta and last MMR."""
    
    def __init__(self, 
                 a_win_prob: List[float], b_win_prob: List[float], 
                 last_mmr: Dict[str, float], last_date_mmr: Dict[str, float], total_delta: Dict[str, float],
                 base_mmr_delta: float, gamma: float):
        # Shared state references
        self.last_mmr = last_mmr
        self.last_date_mmr = last_date_mmr
        self.total_delta = total_delta
        self.a_win_prob = a_win_prob
        self.b_win_prob = b_win_prob
        
        # Hyperparameters
        self.base_mmr_delta = base_mmr_delta
        self.gamma = gamma

    def _get_win_prob(self, mmr_diff: float):
        self.a_win_prob[0] = 1 / (1 + 10 ** (mmr_diff / self.gamma))
        self.b_win_prob[0] = 1 - self.a_win_prob[0]
        return
    
    @abstractmethod
    def _calculate_win_probability(self, *args: Any) -> float:
        pass

    @abstractmethod
    def apply_match_outcome(self, *args: Any):
        pass
    

class FifaTeamMatchHandler(TeamMatchHandler):
    """FIFA-specific team match handler with star ratings."""
    def __init__(self, 
                 a_win_prob: List[float], b_win_prob: List[float], 
                 last_mmr: Dict[str, float], last_date_mmr: Dict[str, float], total_delta: Dict[str, float], 
                 base_mmr_delta: float, gamma: float, star_rating_factor: float):
        super().__init__(a_win_prob, b_win_prob, last_mmr, last_date_mmr, total_delta, base_mmr_delta, gamma)
        # Hyperparameters
        self.star_rating_factor = star_rating_factor
    
    def _calculate_win_probability(self, home_player: str, away_player: str, stars_home: float, stars_away: float):
        home_base_mmr = self.last_date_mmr[home_player]
        away_base_mmr = self.last_date_mmr[away_player]
        
        star_factor = self.star_rating_factor * (stars_home - stars_away) / 2
        
        home_effective_mmr = home_base_mmr + star_factor
        away_effective_mmr = away_base_mmr - star_factor

        self._get_win_prob(away_effective_mmr - home_effective_mmr)
        
        return
    
    def apply_match_outcome(self, home_player: str, away_player: str, stars_home: float, stars_away: float, score: List[int]):
        """score is a list of [home_score, away_score, home_penalties_score, away_penalties_score]"""

        self._calculate_win_probability(home_player, away_player, stars_home, stars_away)

        home_score, away_score, home_penalties_score, away_penalties_score = score

        if home_score != away_score:
            home_won = home_score > away_score
            penalties = False
        elif home_penalties_score != away_penalties_score: 
            home_won = home_penalties_score > away_penalties_score
            penalties = True
        else:
            home_won = 0.5  # Draw
            penalties = False

        home_match_delta = self.base_mmr_delta * (home_won - self.a_win_prob[0]) * 2 # Full delta at 50% win prob

        if penalties:
            home_match_delta *= 0.5

        self.total_delta[home_player] += home_match_delta
        self.total_delta[away_player] += -home_match_delta
        self.last_mmr[home_player] += home_match_delta
        self.last_mmr[away_player] += -home_match_delta
        
        return
    

class RLTeamMatchHandler(TeamMatchHandler):
    """Rocket League-specific team match handler with different team size handling."""
    def __init__(self, 
                 a_win_prob: List[float], b_win_prob: List[float], 
                 last_mmr: Dict[str, float], last_date_mmr: Dict[str, float], total_delta: Dict[str, float], 
                 base_mmr_delta: float, gamma: float, k_factor: float):
        super().__init__(a_win_prob, b_win_prob, last_mmr, last_date_mmr, total_delta, base_mmr_delta, gamma)
        # Hyperparameters
        self.k_factor = k_factor

    def _calculate_win_probability(self, blue_team: List[str], orange_team: List[str]):
        size_a = len(blue_team)
        size_b = len(orange_team)
        
        mmr_a = sum(self.last_date_mmr[p] for p in blue_team) * size_a ** (self.k_factor - 1)
        mmr_b = sum(self.last_date_mmr[p] for p in orange_team) * size_b ** (self.k_factor - 1)
        
        return self._get_win_prob((mmr_b - mmr_a)/((size_a + size_b)/2))

    def apply_match_outcome(self, blue_team: List[str], orange_team: List[str], score: List[int], overtime: bool) -> Dict[str, float]:
        """score is a list of [blue_score, orange_score]"""

        self._calculate_win_probability(blue_team, orange_team)

        blue_score, orange_score = score
        blue_won = blue_score > orange_score
        
        blue_size = len(blue_team)
        orange_size = len(orange_team)
        
        blue_base_delta = self.base_mmr_delta * (blue_won - self.a_win_prob[0]) * 2 # Full delta at 50% win prob
        
        if overtime:
            blue_base_delta *= 0.5
        
        blue_match_delta = blue_base_delta * orange_size / blue_size
        orange_match_delta = -blue_base_delta * blue_size / orange_size
        
        for player in blue_team:
            self.total_delta[player] += blue_match_delta
            self.last_mmr[player] += blue_match_delta
        
        for player in orange_team:
            self.total_delta[player] += orange_match_delta
            self.last_mmr[player] += orange_match_delta
        
        return

    

