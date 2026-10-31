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

"""What a card carries into its BUD: title, requirements, Figma link, priority, repos.

The requirements are the card's current PRD (else its description), then a
"From the board" section: the checklist, the attachments as links, the
design brief and a link back to the card. Copied once; later card edits
don't reach the BUD.
"""

from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.board_card import BoardCard
from app.models.board_card_detail import BoardCardAttachment, BoardCardChecklistItem
from app.models.board_enums import BoardAttachmentKind, BoardCardDocKind
from app.models.bud import BUDPriority
from app.models.tracked_repository import TrackedRepository
from app.repositories.board_card_checklist import BoardCardChecklistRepository
from app.repositories.board_card_doc import BoardCardDocRepository
from app.repositories.board_card_thread import BoardCardAttachmentRepository
from app.repositories.board_repo import BoardRepoRepository
from app.schemas.boards.handover import ImpactedRepo
from app.schemas.bud import is_figma_url
from app.services.boards.access import BoardAccess
from app.services.boards.card_notify import card_path
from app.services.boards.reads import card_key

# A card with no priority hands over at the BUD default.
FALLBACK_PRIORITY = BUDPriority.P2
FROM_THE_BOARD = "## From the board"


@dataclass(frozen=True)
class HandoverDraft:
    """The BUD a card would become, before the dialog's edits."""

    title: str
    # The PRD or description alone; empty when the card has neither.
    source_md: str
    requirements_md: str
    figma_url: str | None
    priority: BUDPriority
    impacted_repos: list[ImpactedRepo]
    checklist_open: int


def impacted(repos: list[TrackedRepository]) -> list[ImpactedRepo]:
    """Repositories in the shape ``bud_documents.impacted_repos`` holds."""
    return [ImpactedRepo(repo_id=repo.id, repo_name=repo.name) for repo in repos]


async def draft_for(db: AsyncSession, access: BoardAccess, card: BoardCard) -> HandoverDraft:
    """Read the card and build its draft; writes nothing."""
    docs = BoardCardDocRepository(db, org_id=access.org_id)
    prd = await docs.current(card.id, BoardCardDocKind.PRD)
    brief = await docs.current(card.id, BoardCardDocKind.DESIGN_BRIEF)
    items = await BoardCardChecklistRepository(db, org_id=access.org_id).list_for_card(card.id)
    attachments = await BoardCardAttachmentRepository(db, org_id=access.org_id).list_for_parent(
        card.id
    )
    source = (prd.body_md if prd is not None else card.description_md or "").strip()
    section = _from_the_board(access, card, items, attachments, brief.body_md if brief else None)
    return HandoverDraft(
        title=card.title,
        source_md=source,
        requirements_md=f"{source}\n\n{section}" if source else section,
        figma_url=_figma_url(attachments),
        priority=card.priority or FALLBACK_PRIORITY,
        impacted_repos=await _repos(db, access, card),
        checklist_open=sum(1 for item in items if not item.done),
    )


async def _repos(db: AsyncSession, access: BoardAccess, card: BoardCard) -> list[ImpactedRepo]:
    """The card's repository, else every repository the board links (active ones only)."""
    links = BoardRepoRepository(db, org_id=access.org_id)
    if card.repo_id is not None:
        repo = await links.active_repo(card.repo_id)
        if repo is not None:
            return impacted([repo])
    return impacted(await links.list_linked(access.board.id))


def _figma_url(attachments: list[BoardCardAttachment]) -> str | None:
    """The first link attachment that is a Figma URL."""
    for item in attachments:
        if item.kind is BoardAttachmentKind.LINK and item.url and is_figma_url(item.url):
            return item.url
    return None


def _md_text(text: str) -> str:
    """Text safe inside a markdown link label."""
    return text.replace("\\", "\\\\").replace("[", "\\[").replace("]", "\\]")


def _checklist_md(items: list[BoardCardChecklistItem]) -> str:
    """The checklist as a markdown task list, each named group as a parent item."""
    lines = ["**Checklist**", ""]
    group: str | None = None
    for item in items:
        if item.group_name and item.group_name != group:
            group = item.group_name
            lines.append(f"- {group}")
        indent = "  " if group else ""
        lines.append(f"{indent}- [{'x' if item.done else ' '}] {item.text}")
    return "\n".join(lines)


def _attachments_md(attachments: list[BoardCardAttachment], key: str, url: str) -> str:
    """Links as links; files are named and point at the card that holds them."""
    lines = ["**Attachments**", ""]
    for item in attachments:
        name = _md_text(item.filename or item.url or "")
        if item.kind is BoardAttachmentKind.LINK and item.url:
            lines.append(f"- [{name}]({item.url})")
        else:
            lines.append(f"- {name} (a file on [{key}]({url}))")
    return "\n".join(lines)


def _from_the_board(
    access: BoardAccess,
    card: BoardCard,
    items: list[BoardCardChecklistItem],
    attachments: list[BoardCardAttachment],
    brief_md: str | None,
) -> str:
    key = card_key(access.board.key, card.number)
    url = f"{settings.frontend_url}{card_path(access.board.key, card.number)}"
    parts = [FROM_THE_BOARD]
    if items:
        parts.append(_checklist_md(items))
    if attachments:
        parts.append(_attachments_md(attachments, key, url))
    if brief_md and brief_md.strip():
        parts.append(f"**Design brief**\n\n{brief_md.strip()}")
    parts.append(f"Handed over from [{key}]({url}).")
    return "\n\n".join(parts)
