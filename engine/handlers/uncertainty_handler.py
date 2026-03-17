"""Uncertainty handler for MMR calculation engines."""
from collections import defaultdict
import logging
from typing import Dict


class UncertaintyHandler:
    """Handles uncertainty amplification and reduction."""
    
    def __init__(self, base_mmr_delta: float, uncertainty_decay: float, uncertainty_increase: float, 
                 base_uncertainty: float, logger_name: str = "rl_engine_handlers"):
        self.base_mmr_delta = base_mmr_delta
        self.uncertainty_decay = uncertainty_decay
        self.uncertainty_increase = uncertainty_increase
        self.base_uncertainty = base_uncertainty
        self.logger = logging.getLogger(logger_name)

        self.uncertainty_deltas = {}
        self.current_date_uncertainty_factors_and_deltas = defaultdict(list)
        self.last_date_uncertainty_factors = defaultdict(lambda: base_uncertainty)
        self.inactivity_days = {}
        self.uncertainty_delta_corrections = {}

        self.uncertainty_factors = defaultdict(lambda: base_uncertainty)

    def get_uncertainty_factors(self) -> Dict[str, float]:
        return self.uncertainty_factors

    def get_uncertainty_deltas(self) -> Dict[str, float]:
        return self.uncertainty_deltas

    def get_inactivity_days(self) -> Dict[str, int]:
        return self.inactivity_days
    
    def process_uncertainty(self, base_deltas: Dict[str, float], inactivity_days: Dict[str, int]):

        if inactivity_days:

            self.current_date_uncertainty_factors_and_deltas.clear()

            for player, days in inactivity_days.items():
                uncertainty_diff = self.uncertainty_increase * days
                new_uncertainty = self.uncertainty_factors[player] + uncertainty_diff
                if new_uncertainty < self.base_uncertainty:
                    self.uncertainty_factors[player] = round(new_uncertainty, 6)
                else:
                    inactivity_days[player] = int((new_uncertainty - self.base_uncertainty) / self.uncertainty_increase)
                    self.uncertainty_factors[player] = self.base_uncertainty
            self.last_date_uncertainty_factors.update(self.uncertainty_factors)
            

        self.inactivity_days = inactivity_days

        self.uncertainty_deltas = {}
        self.uncertainty_delta_corrections = {}
        for player, delta in base_deltas.items():

            # History tuple layout: (uncertainty_factor_before_match, base_delta, applied_uncertainty_delta)
            history = self.current_date_uncertainty_factors_and_deltas[player]
            current_factor = self.uncertainty_factors[player]

            factors_so_far = [factor for factor, _, _ in history]
            base_deltas_so_far = [base_delta for _, base_delta, _ in history]
            applied_uncertainty_so_far = [applied_uncertainty_delta for _, _, applied_uncertainty_delta in history]

            factors_with_current = factors_so_far + [current_factor]
            base_deltas_with_current = base_deltas_so_far + [delta]
            average_uncertainty_factor = sum(factors_with_current) / len(factors_with_current)

            # Target: cumulative uncertainty contribution equals using daily average factor.
            target_cumulative_uncertainty = sum(base_deltas_with_current) * (average_uncertainty_factor - 1)
            current_uncertainty_delta = target_cumulative_uncertainty - sum(applied_uncertainty_so_far)

            self.uncertainty_deltas[player] = current_uncertainty_delta
            self.uncertainty_delta_corrections[player] = (
                current_uncertainty_delta - delta * (current_factor - 1)
            )

            history.append((current_factor, delta, current_uncertainty_delta))

            self.uncertainty_factors[player] = round(
                max(1.0, self.uncertainty_factors[player] - self.uncertainty_decay), 6
            )

        self.logger.info(
            "UNCERTAINTY_HANDLER | uncertainty_deltas=%s | uncertainty_delta_correction=%s | uncertainty_factors=%s | inactivity_days=%s",
            {k: round(v, 3) for k, v in sorted(self.uncertainty_deltas.items())},
            {k: round(v, 3) for k, v in sorted(self.uncertainty_delta_corrections.items())},
            {k: round(v, 3) for k, v in sorted(self.uncertainty_factors.items())},
            dict(sorted(self.inactivity_days.items())),
        )
        
        return
