from abc import abstractmethod
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

        self.alpha = alpha
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
                e_blue += 1 / (1 + 10**(self.mmr_matrix[orange][blue] / self.gamma)) / n_2
            
        blue_delta = base_delta * (blue_won - e_blue)

        for blue_updating in blue_team_indices:
            for orange_updating in orange_team_indices:
                self.mmr_matrix[orange_updating][blue_updating] -= blue_delta
                self.mmr_matrix[blue_updating][orange_updating] += blue_delta

        global_mmrs = self.get_global_matrix_mmrs()
        for p, i in self.player_indices.items():
            self.mmr_matrix[i][i] = global_mmrs[p]

        # print(f"Blue Win Prob: {e_blue:.4f} | Blue Delta: {blue_delta:.4f}")

        return e_blue, 1 - e_blue
    
    def get_global_matrix_mmrs(self) -> dict:
        n = len(self.player_indices)
        if n == 0:
            return {}
        
        # print("\n\nCalculating global MMRs:")

        global_mmrs = {}
        for player, i in self.player_indices.items():
            global_mmrs[player] = 0

            # print(f"\nPlayer: {player}")

            for j in range(n):
                if i == j:
                    continue

                player_contribution = 0

                direct_value = 1 / (1 + 10**(-self.mmr_matrix[i][j] / self.gamma))
                direct_value += 0.5
                direct_value *= self.alpha / (n - 2 + self.alpha)
                direct_value /= (n - 1)
                direct_value *= self.base_mmr
                player_contribution += direct_value
                global_mmrs[player] += direct_value

                # print(f"Direct MMR vs {list(self.player_indices.keys())[j]}: {direct_value:.4f} (neutral: {self.base_mmr * self.alpha / (n - 2 + self.alpha) / (n - 1):.4f})")

                for k in range(n):
                    if k == i or k == j:
                        continue

                    collateral_contribution = 1 / (1 + 10**(-(self.mmr_matrix[i][k] - self.mmr_matrix[j][k]) / self.gamma))
                    collateral_contribution += 0.5
                    collateral_contribution *= (1 / (n - 2 + self.alpha))
                    collateral_contribution /= (n - 1)
                    collateral_contribution *= self.base_mmr
                    player_contribution += collateral_contribution
                    global_mmrs[player] += collateral_contribution

                    # print(f"Collateral contribution from {list(self.player_indices.keys())[k]}: {collateral_contribution:.4f} (neutral: {self.base_mmr / (n - 2 + self.alpha) / (n - 1):.4f})")
                
                # print(f"Total contribution from {list(self.player_indices.keys())[j]}: {player_contribution:.4f} (neutral: {self.base_mmr / (n - 1):.4f})")
            
        return global_mmrs

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