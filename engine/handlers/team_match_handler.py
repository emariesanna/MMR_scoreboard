"""Team match handler for MMR calculation engines."""
from abc import ABC, abstractmethod
from collections import defaultdict
from datetime import datetime
import logging
from typing import Any, DefaultDict, Dict, List


class TeamMatchHandler(ABC):
    """Calculates MMR delta from match outcome and win probabilities."""
    
    def __init__(self, base_mmr_delta: float, gamma: float, logger_name: str = "rl_engine_handlers"):
        self.base_mmr_delta = base_mmr_delta
        self.gamma = gamma
        self.logger = logging.getLogger(logger_name)

        self.last_date = None
        self.last_date_mmrs = defaultdict(float)
        self.match_deltas = {}
        self.a_win_prob = 0.0
        self.b_win_prob = 0.0

    def get_win_prob(self) -> tuple[float, float]:
        return self.a_win_prob, self.b_win_prob
    
    def get_match_deltas(self) -> Dict[str, float]:
        return self.match_deltas
    
    @abstractmethod
    def process_match_outcome(self, *args: Any):
        pass

    def _win_prob_formula(self, mmr_diff: float):
        self.a_win_prob = 1 / (1 + 10 ** (mmr_diff / self.gamma))
        self.b_win_prob = 1 - self.a_win_prob
        return
    
    @abstractmethod
    def _calculate_win_probability(self, *args: Any):
        pass


class FifaTeamMatchHandler(TeamMatchHandler):
    """Team match handler with a single player per team, star ratings and penalties."""
    def __init__(self, base_mmr_delta: float, gamma: float, star_rating_factor: float,
                 logger_name: str = "rl_engine_handlers"):
        super().__init__(base_mmr_delta, gamma, logger_name)
        self.star_rating_factor = star_rating_factor
    
    def _calculate_win_probability(self, stars_home: float, stars_away: float, home_mmr: float, away_mmr: float):
        star_factor = self.star_rating_factor * (stars_home - stars_away) / 2
        
        home_effective_mmr = home_mmr + star_factor
        away_effective_mmr = away_mmr - star_factor

        self._win_prob_formula(away_effective_mmr - home_effective_mmr)
        
        return
    
    def process_match_outcome(self, 
                              date_val: datetime,
                              home_player: str, away_player: str, 
                              stars_home: float, stars_away: float, 
                              home_score: int, away_score: int, 
                              home_penalties_score: int, away_penalties_score: int,
                              player_mmrs: DefaultDict[str, float]):

        if self.last_date is None or date_val > self.last_date:
            self.last_date = date_val
            self.last_date_mmrs = player_mmrs.copy()

        self._calculate_win_probability(stars_home, stars_away, 
                                        self.last_date_mmrs[home_player], 
                                        self.last_date_mmrs[away_player])

        if home_score != away_score:
            home_won = home_score > away_score
            penalties = False
        elif home_penalties_score != away_penalties_score: 
            home_won = home_penalties_score > away_penalties_score
            penalties = True
        else:
            home_won = 0.5  # Draw
            penalties = False

        home_match_delta = self.base_mmr_delta * (home_won - self.a_win_prob) * 2 # Full delta at 50% win prob

        if penalties:
            home_match_delta *= 0.5

        self.match_deltas = {
            home_player: home_match_delta,
            away_player: -home_match_delta
        }

        self.logger.info(
            "TEAM_MATCH_HANDLER | win_prob=(%.4f, %.4f) | match_deltas=%s",
            self.a_win_prob,
            self.b_win_prob,
            {k: round(v, 3) for k, v in sorted(self.match_deltas.items())},
        )

        return


class RLTeamMatchHandler(TeamMatchHandler):
    """Team match handler with different team size handling and overtime support."""
    def __init__(self, base_mmr_delta: float, gamma: float, k_factor: float,
                 logger_name: str = "rl_engine_handlers"):
        super().__init__(base_mmr_delta, gamma, logger_name)
        self.k_factor = k_factor

    def process_match_outcome(self, 
                              date_val: datetime,
                              blue_team: List[str], orange_team: List[str], 
                              blue_score: int, orange_score: int, overtime: bool,
                              player_mmrs: DefaultDict[str, float]):
        
        if self.last_date is None or date_val > self.last_date:
            self.last_date = date_val
            self.last_date_mmrs = player_mmrs.copy()

        self._calculate_win_probability([self.last_date_mmrs[p] for p in blue_team], 
                                        [self.last_date_mmrs[p] for p in orange_team])

        blue_won = blue_score > orange_score
        
        blue_size = len(blue_team)
        orange_size = len(orange_team)
        
        blue_base_delta = self.base_mmr_delta * (blue_won - self.a_win_prob) * 2 # Full delta at 50% win prob
        
        if overtime:
            blue_base_delta *= 0.5
        
        blue_match_delta = blue_base_delta * orange_size / blue_size
        orange_match_delta = -blue_base_delta * blue_size / orange_size

        self.match_deltas = {player: blue_match_delta for player in blue_team}
        self.match_deltas.update({player: orange_match_delta for player in orange_team})


        self.logger.info(
            "TEAM_MATCH_HANDLER | win_prob=(%.4f, %.4f) | match_deltas=%s",
            self.a_win_prob,
            self.b_win_prob,
            {k: round(v, 3) for k, v in sorted(self.match_deltas.items())},
        )

        return

    def _calculate_win_probability(self, blue_team_mmr: List[float], orange_team_mmr: List[float]):
        print(f"blue team MMRs: {blue_team_mmr} - orange team MMRs: {orange_team_mmr}")
        size_a = len(blue_team_mmr)
        size_b = len(orange_team_mmr)

        mmr_a = sum(blue_team_mmr) # * size_a ** (self.k_factor - 1)
        mmr_b = sum(orange_team_mmr) # * size_b ** (self.k_factor - 1)
        
        self._win_prob_formula((mmr_b - mmr_a)/((size_a + size_b)/2))

        return

if __name__ == "__main__":
    k_factor = 1
    blue_team_mmr = [1118.8297428227604, 1000]
    orange_team_mmr = [1280.7905228723969, 691.1367909622451]
    handler = RLTeamMatchHandler(base_mmr_delta=25, gamma=800, k_factor=k_factor)
    handler._calculate_win_probability(blue_team_mmr=blue_team_mmr, orange_team_mmr=orange_team_mmr)
    mmr_a = sum(blue_team_mmr) * len(blue_team_mmr) ** (k_factor - 1)
    mmr_b = sum(orange_team_mmr) * len(orange_team_mmr) ** (k_factor - 1)
    print(f"Blue win prob: {handler.get_win_prob()[0]:.4f}, Orange win prob: {handler.get_win_prob()[1]:.4f}")
    print(f"mmr_a: {mmr_a:.2f}, mmr_b: {mmr_b:.2f}, mmr_diff: {(mmr_b - mmr_a)/((len(blue_team_mmr) + len(orange_team_mmr))/2):.2f}")