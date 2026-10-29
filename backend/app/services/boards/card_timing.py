# Copyright 2025-2026 Arun Rajkumar
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""When a card started and finished, from the categories of the stages it enters.

``started_at`` is the first entry into an ``in_progress`` stage and is
never cleared. ``completed_at`` is set on entering ``done`` or
``canceled`` and cleared when the card goes back to ``todo`` or
``in_progress``. ``BoardCardPositionRepository.move_all`` applies the same
rule in SQL when a deleted stage's cards move.
"""

from datetime import datetime

from app.models.board_card import BoardCard
from app.models.board_enums import COMPLETED_CATEGORIES, BoardStageCategory


def enter_category(card: BoardCard, category: BoardStageCategory, now: datetime) -> None:
    """Update the card's started and completed stamps for entering ``category``."""
    if category is BoardStageCategory.IN_PROGRESS and card.started_at is None:
        card.started_at = now
    if category in COMPLETED_CATEGORIES:
        if card.completed_at is None:
            card.completed_at = now
    else:
        card.completed_at = None
