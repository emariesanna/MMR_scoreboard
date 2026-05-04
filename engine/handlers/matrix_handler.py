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
    def __init__(self, base_mmr: float, base_mmr_delta: float, beta: float, gamma: float, goal_difference_factor: float, matrix_decay_per_day: float):
        super().__init__(base_mmr, base_mmr_delta)

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

    def predict_win_prob(self, blue_team: List[str], orange_team: List[str]) -> tuple[float, float]:
        total_diff = 0
        valid_pairs = 0
        for blue in blue_team:
            for orange in orange_team:
                if blue in self.player_indices and orange in self.player_indices:
                    b_idx = self.player_indices[blue]
                    o_idx = self.player_indices[orange]
                    total_diff += self.mmr_matrix[b_idx][o_idx]
                    valid_pairs += 1
        
        avg_diff = total_diff / valid_pairs if valid_pairs > 0 else 0
        prob_blue = 1 / (1 + 10 ** (-avg_diff / self.gamma))
        prob_orange = 1 - prob_blue
        return prob_blue, prob_orange

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
        base_delta = self.base_mmr_delta * (1 + (abs(blue_score - orange_score)-1) / self.goal_difference_factor) * (0.5 if overtime else 1)

        old_matrix = [row[:] for row in self.mmr_matrix]
        outcome = 1 if blue_won else 0
        collateral_matches = (len(blue_team_indices) * len(orange_team_indices)) - 1
        
        index_to_player = {idx: p for p, idx in self.player_indices.items()}

        for blue_updating in blue_team_indices:
            for orange_updating in orange_team_indices:

                e_blue = 1 / (1 + 10**(old_matrix[orange_updating][blue_updating] / self.gamma))
                direct_delta = base_delta * (outcome - e_blue) * (1 - self.beta if collateral_matches > 0 else 1)
                total_delta = direct_delta

                print(f"Updating {index_to_player[blue_updating]} vs {index_to_player[orange_updating]} | old_MMR: {old_matrix[blue_updating][orange_updating]:.4f} | e_blue: {e_blue:.4f} | score: {blue_score}-{orange_score} OT: {overtime} | direct_delta: {direct_delta:.4f}")

                if collateral_matches > 0:
                    for blue in blue_team_indices:
                        for orange in orange_team_indices:
                            if (blue == blue_updating and orange == orange_updating):
                                continue
                        
                            e_blue = 1 / (1 + 10**(old_matrix[orange][blue] / self.gamma))
                            collateral_delta = base_delta * (outcome - e_blue) * (self.beta) / collateral_matches
                            total_delta += collateral_delta

                            print(f"Collateral {index_to_player[blue]} vs {index_to_player[orange]} | old_MMR: {old_matrix[orange][blue]:.4f} | e_blue: {e_blue:.4f} | contribution: {collateral_delta:.4f}") 

                self.mmr_matrix[blue_updating][orange_updating] += total_delta
                self.mmr_matrix[orange_updating][blue_updating] -= total_delta

        global_mmrs = self.get_global_matrix_mmrs()
        for p, i in self.player_indices.items():
            self.mmr_matrix[i][i] = global_mmrs[p]

        return
    
    def get_global_matrix_mmrs(self) -> dict:
        n = len(self.player_indices)
        if n == 0:
            return {}
        
        print("\n\nCalculating global MMRs:")

        global_mmrs = {}
        for player, i in self.player_indices.items():
            global_mmrs[player] = 0

            print(f"\nPlayer: {player}")

            for j in range(n):
                if i == j:
                    continue

                direct_value = 1 / (1 + 10**(-self.mmr_matrix[i][j] / self.gamma))
                avg_collateral_value = 0

                print(f"Direct MMR vs {list(self.player_indices.keys())[j]}: {direct_value:.4f}")

                for k in range(n):
                    if k == i or k == j:
                        continue

                    collateral_contribution = 1 / (1 + 10**(-(self.mmr_matrix[i][k] - self.mmr_matrix[j][k]) / self.gamma))
                    avg_collateral_value += collateral_contribution

                    print(f"Collateral contribution from {list(self.player_indices.keys())[k]}: {collateral_contribution:.4f}")

                avg_collateral_value /= (n - 2)

                global_mmrs[player] += direct_value + avg_collateral_value

            global_mmrs[player] *= self.base_mmr / (n - 1)
            
        return global_mmrs
    
    def get_global_matrix_mmrs_old(self) -> dict:
        n = len(self.player_indices)
        if n == 0:
            return {}

        global_mmrs = {}
        for player, i in self.player_indices.items():
            weighted_score_sum = 0
            
            for j in range(n):
                if i == j:
                    continue

                col_avg = 0
                for k in range(n):
                    if k == i or k == j:
                        continue
                    col_avg += self.mmr_matrix[k][j]
                col_avg /= n - 1
                
                m_ij = self.mmr_matrix[i][j]

                weight = 1 / (1 + 10**(col_avg / self.gamma))
                weight += 0.5
                
                weighted_score_sum += (m_ij * weight)
                
            global_mmrs[player] = weighted_score_sum
            
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
    handler = RLMatrixHandler(base_mmr=0, base_mmr_delta=30, beta=0.5, gamma=800, goal_difference_factor=6)
    handler.process_match_outcome(
        blue_team=["Alice", "Bob"], orange_team=["Charlie", "David"], 
        blue_score=3, orange_score=1, overtime=False
    )
    print_matrix(handler.mmr_matrix, handler.player_indices)