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

"""Trello as an :class:`~app.services.imports.source.ImportSource`.

In API mode, discovery first fetches the board and every comment and
stores them as the session's file; from then on both modes read the same
stored JSON. Files are downloaded (API mode only) during prefetch, before
the batch takes its locks.
"""

import asyncio
import json
import uuid
from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.external_import import ExternalImportSession, ImportMode, ImportSourceKind
from app.repositories.import_people import ImportPeopleRepository
from app.schemas.boards.import_mapping import ArchivedChoice, StageChoice
from app.services.attachment_upload import StoredFile
from app.services.imports.context import ImportContext
from app.services.imports.errors import ImportSourceDataError, ImportStateError
from app.services.imports.source import ExternalItem, ImportDiscovery
from app.services.imports.storage import load_source_file, store_source_file
from app.services.imports.target import session_mapping
from app.services.imports.trello import client as trello_client
from app.services.imports.trello.cards import CardDraft, card_drafts
from app.services.imports.trello.client import TrelloClient
from app.services.imports.trello.constants import SNAPSHOT_FILENAME
from app.services.imports.trello.credentials import load_credentials
from app.services.imports.trello.discovery import build_discovery
from app.services.imports.trello.files import fetch_files, remove_files
from app.services.imports.trello.parse import TrelloExport, parse_export
from app.services.imports.trello.plan import TrelloPlan, build_plan
from app.services.imports.trello.writer import write_card

NO_SOURCE_FILE = "This import has no board data yet."
NO_BOARD_REF = "This import doesn't name a Trello board."
NOT_PREPARED = "The import wasn't prepared before writing."

SKIP_LIST = "list_skipped"
SKIP_ARCHIVED = "archived"
SKIP_NO_LIST = "list_missing"


class TrelloSource:
    """One run's view of one Trello board."""

    kind = ImportSourceKind.TRELLO

    def __init__(self) -> None:
        self._export: TrelloExport | None = None
        self._drafts: list[CardDraft] | None = None
        self._plan: TrelloPlan | None = None
        self._client: TrelloClient | None = None
        self._files: dict[str, dict[str, StoredFile]] = {}

    async def discover(self, db: AsyncSession, session: ExternalImportSession) -> ImportDiscovery:
        """Summarise the board for review, fetching it from Trello first in API mode."""
        if session.mode is ImportMode.API:
            await self._snapshot(db, session)
        export, drafts = await self._load(session)
        people = await ImportPeopleRepository(db, org_id=session.org_id).active_names()
        summary = build_discovery(export, drafts, people, session.mode)
        return ImportDiscovery(total_items=len(drafts), summary=summary.model_dump(mode="json"))

    async def prepare(self, ctx: ImportContext) -> None:
        """Stages, people and labels on the board; a Trello client in API mode."""
        export, _ = await self._load(ctx.session)
        self._plan = await build_plan(ctx, export, session_mapping(ctx.session))
        if ctx.session.mode is ImportMode.API and self._client is None:
            creds = await load_credentials(ctx.db, ctx.org_id)
            self._client = trello_client.new_client(creds)

    async def iter_items(self, session: ExternalImportSession) -> AsyncIterator[ExternalItem]:
        """Every card in import order, with why the mapping skips it, if it does."""
        mapping = session_mapping(session)
        actions = {entry.list_id: entry.action for entry in mapping.lists}
        _, drafts = await self._load(session)
        for index, draft in enumerate(drafts):
            yield ExternalItem(
                index=index,
                external_id=draft.id,
                payload=draft,
                skip_reason=_skip_reason(
                    draft, actions.get(draft.list_id), mapping.archived_cards
                ),
            )

    async def prefetch(self, item: ExternalItem, ctx: ImportContext) -> None:
        """Copy the card's uploaded files (API mode)."""
        if self._client is None:
            return
        draft = _draft(item)
        self._files[draft.id] = await fetch_files(self._client, ctx, draft.id, draft.attachments)

    async def write_item(self, item: ExternalItem, ctx: ImportContext) -> uuid.UUID:
        """Write the card; its copied files are handed over to it."""
        if self._plan is None:
            raise ImportStateError(NOT_PREPARED)
        card_id = await write_card(
            ctx, self._plan, _draft(item), self._files.get(item.external_id, {})
        )
        self._files.pop(item.external_id, None)
        return card_id

    async def discard(self, item: ExternalItem) -> None:
        """Delete files copied for a card that wasn't written."""
        await remove_files(self._files.pop(item.external_id, {}).values())

    async def close(self) -> None:
        """Close the Trello client, if one was opened."""
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def _snapshot(self, db: AsyncSession, session: ExternalImportSession) -> None:
        if not session.source_ref:
            raise ImportSourceDataError(NO_BOARD_REF)
        client = self._client or trello_client.new_client(
            await load_credentials(db, session.org_id)
        )
        self._client = client
        board = await client.board(session.source_ref)
        board["actions"] = await client.comments(str(board.get("id", "")))
        data = json.dumps(board).encode()
        session.storage_path = await store_source_file(
            session.org_id, session.id, SNAPSHOT_FILENAME, data
        )

    async def _load(self, session: ExternalImportSession) -> tuple[TrelloExport, list[CardDraft]]:
        if self._export is None or self._drafts is None:
            if not session.storage_path:
                raise ImportSourceDataError(NO_SOURCE_FILE)
            data = await load_source_file(session.storage_path)
            self._export = await asyncio.to_thread(parse_export, data)
            self._drafts = card_drafts(self._export)
        return self._export, self._drafts


def _draft(item: ExternalItem) -> CardDraft:
    if not isinstance(item.payload, CardDraft):
        raise TypeError("a Trello item carries a card draft")
    return item.payload


def _skip_reason(
    draft: CardDraft, action: StageChoice | None, archived: ArchivedChoice
) -> str | None:
    if action is None:
        return SKIP_NO_LIST
    if action is StageChoice.SKIP:
        return SKIP_LIST
    if draft.closed and archived is ArchivedChoice.SKIP:
        return SKIP_ARCHIVED
    return None
