from abc import abstractmethod
from typing import Any, List

class MatrixHandler():
    def __init__(self, base_mmr: float, base_mmr_delta: float):
        self.player_indices = {}
        self.mmr_matrix = []
        self.base_mmr = base_mmr
        self.base_mmr_delta = base_mmr_delta
        
    @abstractmethod
    def process_match_outcome(self, *args: Any):
        pass    
    @abstractmethod
    def predict_win_prob(self, *args: Any):
        pass

class RLMatrixHandler(MatrixHandler):
    def __init__(self, base_mmr: float, base_mmr_delta: float, beta: float, gamma: float, goal_difference_factor: float):
        super().__init__(base_mmr, base_mmr_delta)

        self.beta = beta
        self.gamma = gamma
        self.goal_difference_factor = goal_difference_factor

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
        """
        Calculates a global holistic MMR summary for each player using exponential weights.
        """
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