from __future__ import annotations

from ..support import *


from .admin_exercises_inventory import ExercisesInventoryMixin
from .admin_training_finance import TrainingFinanceMixin
from .admin_calendar_ranking import CalendarRankingMixin


class AdminPagesMixin(
    ExercisesInventoryMixin,
    TrainingFinanceMixin,
    CalendarRankingMixin,
):
    pass
