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

"""Composite foreign keys shared by the board tables.

Each pairs the referenced id with ``org_id``, so a board row can never
point at another org's board, card or member.
"""

from sqlalchemy import ForeignKeyConstraint


def board_fk(table: str) -> ForeignKeyConstraint:
    """``(board_id, org_id)`` → ``boards(id, org_id)``, cascading deletes."""
    return ForeignKeyConstraint(
        ["board_id", "org_id"],
        ["boards.id", "boards.org_id"],
        ondelete="CASCADE",
        name=f"fk_{table}_board_org",
    )


def card_fk(table: str) -> ForeignKeyConstraint:
    """``(card_id, org_id)`` → ``board_cards(id, org_id)``, cascading deletes."""
    return ForeignKeyConstraint(
        ["card_id", "org_id"],
        ["board_cards.id", "board_cards.org_id"],
        ondelete="CASCADE",
        name=f"fk_{table}_card_org",
    )


def member_fk(table: str) -> ForeignKeyConstraint:
    """``(user_id, org_id)`` → ``org_to_user``: offboarding cascades the row away."""
    return ForeignKeyConstraint(
        ["user_id", "org_id"],
        ["org_to_user.user_id", "org_to_user.org_id"],
        ondelete="CASCADE",
        name=f"fk_{table}_user_org",
    )
