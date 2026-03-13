"""Inactivity handler for MMR calculation engines."""
import datetime
from typing import Dict, List, Set

class InactivityHandler:
    def __init__(self):
        self.last_date = None
        self.inactivity_days = {}

    def get_inactivity_days(self) -> Dict[str, int]:
        return self.inactivity_days

    def process_inactivity(self, current_date: datetime, active_players: Set[str]):
        if self.last_date is None:
            self.inactivity_days = {}
            self.last_date = current_date
            return
        
        if self.last_date == current_date:
            self.inactivity_days = {}
            return

        days_since_last_match = (current_date - self.last_date).days
        for player in active_players:
            self.inactivity_days[player] = self.inactivity_days.get(player, 0) + days_since_last_match
        self.last_date = current_date

        return
            