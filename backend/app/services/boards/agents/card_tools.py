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

"""The card tools a run's MCP token may call: read its card, write a draft on it.

The token's grant names one card and one run. A call naming any other card
(by id or key), from a token with no card grant, on an archived card, or
after the run stopped being active, is refused with :class:`CardGrantError`.
The run's row is locked for the rest of the call, so a cancel (a move to
another board, AI switched off) can't land between the check and the write.
Everything is read inside the grant's org.
"""

import uuid
from dataclasses import dataclass
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.mcp.token_grants import InternalTokenGrant
from app.models.board import Board
from app.models.board_agent import BoardAgentRunStatus, BoardCardAgentRun
from app.models.board_card import BoardCard
from app.models.board_enums import BoardCardDocKind
from app.repositories.board import BoardRepository
from app.repositories.board_agent_run import BoardCardAgentRunRepository
from app.repositories.board_card import BoardCardRepository
from app.services.boards.agents.context import card_context
from app.services.boards.agents.drafts import write_draft
from app.services.boards.reads import card_key

NOT_A_CARD_RUN = "This tool only works inside a board card's agent run."
OTHER_CARD = "This run may only touch its own card."
RUN_OVER = "This agent run has ended; nothing more can be written."
CARD_ARCHIVED = "This card is archived; nothing can be written on it."


class CardGrantError(Exception):
    """The call is outside the token's card grant."""


@dataclass(frozen=True)
class GrantedCard:
    """The card a call may touch, its board and the run the token belongs to."""

    board: Board
    card: BoardCard
    run: BoardCardAgentRun


async def granted_card(
    db: AsyncSession,
    grant: InternalTokenGrant | None,
    *,
    card_id: str | None,
    card_key_value: str | None,
) -> GrantedCard:
    """The grant's card, checked against what the call names.

    Raises:
        CardGrantError: No card grant, another card named, an archived card, or the
            run is over.
    """
    if grant is None or grant.card_id is None or grant.run_id is None:
        raise CardGrantError(NOT_A_CARD_RUN)
    if card_id is not None and _uuid(card_id) != grant.card_id:
        raise CardGrantError(OTHER_CARD)
    card = await BoardCardRepository(db, org_id=grant.org_id).get_by_id(grant.card_id)
    board = (
        await BoardRepository(db, org_id=grant.org_id).get_by_id(card.board_id) if card else None
    )
    if card is None or board is None:
        raise CardGrantError(OTHER_CARD)
    if card_key_value is not None and card_key_value.strip().upper() != card_key(
        board.key, card.number
    ):
        raise CardGrantError(OTHER_CARD)
    # Card, then run: the same order a move between boards and AI switched off take.
    await BoardCardRepository(db, org_id=grant.org_id).lock(card)
    if card.archived_at is not None:
        raise CardGrantError(CARD_ARCHIVED)
    runs = BoardCardAgentRunRepository(db, org_id=grant.org_id)
    run = await runs.get_for_card(card.id, grant.run_id)
    if run is not None:
        await runs.lock(run)
    if run is None or run.status is not BoardAgentRunStatus.RUNNING:
        raise CardGrantError(RUN_OVER)
    return GrantedCard(board=board, card=card, run=run)


def _uuid(value: str) -> uuid.UUID | None:
    try:
        return uuid.UUID(value)
    except ValueError:
        return None


async def read_card(db: AsyncSession, granted: GrantedCard) -> dict[str, Any]:
    """The run's card and what surrounds it."""
    return await card_context(db, granted.board, granted.card)


async def write_card_draft(
    db: AsyncSession, granted: GrantedCard, kind: BoardCardDocKind, content_md: str
) -> dict[str, Any]:
    """Save ``content_md`` as a draft of ``kind`` on the run's card, and commit."""
    doc = await write_draft(
        db, granted.board, granted.card, kind, content_md, run_id=granted.run.id
    )
    await db.commit()
    return {
        "saved": True,
        "card_key": card_key(granted.board.key, granted.card.number),
        "kind": kind.value,
        "version": doc.version,
        "state": doc.state.value,
    }
