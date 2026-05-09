from abc import abstractmethod
import math
from typing import Any, List

class MatrixHandler():
    def __init__(self, base_mmr: float, base_mmr_delta: float):
        self.player_indices = {}
        self.mmr_matrix = []
        self.base_mmr = base_mmr
        self.base_mmr_delta = base_mmr_delta
        self.last_date = None
        
    @abstractmethod
    def process_match_outcome(self, *args: Any):
        pass    
    @abstractmethod
    def predict_win_prob(self, *args: Any):
        pass

class RLMatrixHandler(MatrixHandler):
    def __init__(self, base_mmr: float, base_mmr_delta: float, alpha: float, beta: float, gamma: float, goal_difference_factor: float, matrix_decay_per_day: float):
        super().__init__(base_mmr, base_mmr_delta)
        self.match_count = 0
        self.alpha = alpha
        self.beta = beta
        self.gamma = gamma
        self.goal_difference_factor = goal_difference_factor
        self.matrix_decay_per_day = matrix_decay_per_day

    def process_decay(self, current_date):
        if self.last_date is None:
            self.last_date = current_date
            return
        
        days_passed = (current_date - self.last_date).days
        if days_passed > 0:
            decay_amount = days_passed * self.matrix_decay_per_day
            n = len(self.player_indices)
            for i in range(n):
                for j in range(n):
                    if i != j:
                        if self.mmr_matrix[i][j] > 0:
                            self.mmr_matrix[i][j] = max(0.0, self.mmr_matrix[i][j] - decay_amount)
                        elif self.mmr_matrix[i][j] < 0:
                            self.mmr_matrix[i][j] = min(0.0, self.mmr_matrix[i][j] + decay_amount)
                            
        self.last_date = current_date

    def process_match_outcome(self,
                              blue_team: List[str], orange_team: List[str], 
                              blue_score: int, orange_score: int, overtime: bool):
        
        # Ensure new players have an index and corresponding MMR in the matrix
        for player in blue_team + orange_team:
            if player not in self.player_indices:
                self.player_indices[player] = len(self.player_indices)
                for row in self.mmr_matrix:
                    row.append(0.0)
                self.mmr_matrix.append([0.0] * len(self.player_indices))

        blue_team_indices = [self.player_indices[player] for player in blue_team]
        orange_team_indices = [self.player_indices[player] for player in orange_team]

        blue_won = blue_score > orange_score
        base_delta = 2 * self.base_mmr_delta * (1 + (abs(blue_score - orange_score) - 1) / self.goal_difference_factor) * (0.5 if overtime else 1)

        blue_team_size = len(blue_team)
        orange_team_size = len(orange_team)

        n = max(blue_team_size, orange_team_size)
        n_2 = n**2

        match n:
            case 1:
                base_delta *= 1.5
            case 2:
                pass
            case 3:
                base_delta *= 2/3
            case 4:
                base_delta *= 1/2

        if blue_team_size > orange_team_size:
            e_blue = (blue_team_size - orange_team_size) * blue_team_size / n_2
            # print(f"Blue size: {blue_team_size}, Orange size: {orange_team_size}, initial e_blue: {e_blue:.4f})")
        else:
            e_blue = 0

        for blue in blue_team_indices:
            for orange in orange_team_indices:
                e_blue += 1 / (1 + 10**(self.mmr_matrix[blue][orange] / self.gamma)) / n_2
            
        blue_delta = base_delta * (blue_won - e_blue)

        for blue_updating in blue_team_indices:
            for orange_updating in orange_team_indices:
                self.mmr_matrix[orange_updating][blue_updating] += blue_delta
                self.mmr_matrix[blue_updating][orange_updating] -= blue_delta

        global_mmrs = self.get_global_matrix_mmrs()
        for p, i in self.player_indices.items():
            self.mmr_matrix[i][i] = global_mmrs[p]

        # print(f"Blue Win Prob: {e_blue:.4f} | Blue Delta: {blue_delta:.4f}")

        return e_blue, 1 - e_blue
    
    def get_global_matrix_mmrs(self) -> dict:

        self.match_count += 1

        n = len(self.player_indices)
        if n == 0:
            return {}

        global_mmrs = {}
        for player, i in self.player_indices.items():
            global_mmrs[player] = 0
            global_prob = 0

            for j in range(n):
                if i == j:
                    continue
                
                direct_prob = self._mmr_to_prob(self.mmr_matrix[j][i])
                avg_opponent_prob = 0

                for k in range(n):
                    if k == i or k == j:
                        continue
                    
                    avg_opponent_prob += self._mmr_to_prob(self.mmr_matrix[k][j]) / (n-2)
                
                indirect_prob = direct_prob * avg_opponent_prob
                adapted_indirect_prob = indirect_prob ** 0.5
                global_prob += adapted_indirect_prob / (n-1)
            
            global_mmrs[player] = self._prob_to_mmr(global_prob) + self.base_mmr
                    
        return global_mmrs
    
    def _mmr_to_prob(self, mmr: float) -> float:
        return 1 / (1 + 10**(-mmr / self.gamma))

    def _prob_to_mmr(self, prob: float) -> float:
        return - math.log10((1 - prob) / prob) * self.gamma

def print_matrix(matrix: List[List[float]], player_indices: dict):
    if not matrix:
        print("<empty matrix>")
        return

    index_to_player = {index: player for player, index in player_indices.items()}
    header = [""] + [index_to_player[i] for i in range(len(matrix))]
    print("\t".join(header))
    for i, row in enumerate(matrix):
        print(f"{index_to_player[i]}\t" + "\t".join(f"{mmr:.2f}" for mmr in row))



if __name__ == "__main__":
    handler = RLMatrixHandler(base_mmr=0, base_mmr_delta=30, beta=2.0, gamma=800, goal_difference_factor=6)
    handler.process_match_outcome(
        blue_team=["Alice", "Bob"], orange_team=["Charlie", "David"], 
        blue_score=3, orange_score=1, overtime=False
    )
    print_matrix(handler.mmr_matrix, handler.player_indices)