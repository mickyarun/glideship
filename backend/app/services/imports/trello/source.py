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

Both modes end in the same stored compact board: an upload is parsed when
it's created, and in API mode discovery fetches the board and every
comment, parses them once and stores the result. From then on discovery
and the run read that file. Files are downloaded (API mode only) during
prefetch, with no transaction open and before the batch takes its locks.
"""

import asyncio
from collections.abc import Sequence
from contextlib import AbstractAsyncContextManager
from types import TracebackType
from typing import Any, Self

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.external_import import ExternalImportSession, ImportMode, ImportSourceKind
from app.repositories.import_people import ImportPeopleRepository
from app.schemas.boards.trello_discovery import TrelloDiscovery
from app.services.boards.access import BoardCaller
from app.services.imports.context import ImportContext
from app.services.imports.draft import AttachmentDraft, SourceBoard
from app.services.imports.errors import ImportSourceDataError
from app.services.imports.files import copy_files
from app.services.imports.items import ExternalItem
from app.services.imports.prefetch import FetchedItem, Prefetched, prefetched
from app.services.imports.source import ImportDiscovery, MappingIds
from app.services.imports.storage import load_source_file, store_source_file
from app.services.imports.trello import client as trello_client
from app.services.imports.trello.cards import source_board
from app.services.imports.trello.client import TrelloClient
from app.services.imports.trello.constants import SNAPSHOT_FILENAME
from app.services.imports.trello.credentials import check_api_access, load_credentials
from app.services.imports.trello.discovery import build_discovery
from app.services.imports.trello.models import TrelloExport
from app.services.imports.trello.parse import compact_json, load_compact, parse_board
from app.services.imports.trello.snapshot import fetch_snapshot

NO_SOURCE_FILE = "This import has no board data yet."
NO_BOARD_REF = "This import doesn't name a Trello board."


class TrelloSource:
    """One job's view of one Trello board."""

    kind = ImportSourceKind.TRELLO

    def __init__(self) -> None:
        self._export: TrelloExport | None = None
        self._client: TrelloClient | None = None

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(
        self, kind: type[BaseException] | None, exc: BaseException | None, tb: TracebackType | None
    ) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def check_startable(
        self, db: AsyncSession, session: ExternalImportSession, caller: BoardCaller
    ) -> None:
        """API mode needs ``integrations:configure`` and the org's Trello credentials."""
        if session.mode is ImportMode.API:
            await check_api_access(db, caller)

    def mapping_ids(self, discovery: dict[str, Any]) -> MappingIds:
        """Every Trello list must be mapped; members may be."""
        found = TrelloDiscovery.model_validate(discovery)
        return MappingIds(
            groups=frozenset(lst.id for lst in found.lists),
            members=frozenset(m.id for m in found.members),
        )

    async def discover(self, db: AsyncSession, session: ExternalImportSession) -> ImportDiscovery:
        """Summarise the board for review, fetching it from Trello first in API mode."""
        if session.mode is ImportMode.API:
            await self._snapshot(db, session)
        export = await self._read(session)
        board = source_board(export)
        people = await ImportPeopleRepository(db, org_id=session.org_id).active_names()
        summary = build_discovery(export, board.cards, people, session.mode)
        return ImportDiscovery(
            total_items=len(board.cards), summary=summary.model_dump(mode="json")
        )

    async def load(self, db: AsyncSession, session: ExternalImportSession) -> SourceBoard:
        """The stored board as drafts; opens a Trello client for API mode's files."""
        board = source_board(await self._read(session))
        if session.mode is ImportMode.API and self._client is None:
            creds = await load_credentials(db, session.org_id)
            self._client = trello_client.new_client(creds)
        return board

    def prefetch(
        self, items: Sequence[ExternalItem], ctx: ImportContext
    ) -> AbstractAsyncContextManager[Prefetched]:
        """Copy the cards' uploaded files (API mode); nothing in upload mode."""
        return prefetched(ctx, items, lambda item: self._fetch(item, ctx))

    async def _fetch(self, item: ExternalItem, ctx: ImportContext) -> FetchedItem:
        client = self._client
        if client is None:
            return FetchedItem()

        async def download(attachment: AttachmentDraft, limit: int) -> bytes | None:
            try:
                card_id = item.external_id
                return await client.download(card_id, attachment.id, attachment.name, limit)
            except ImportSourceDataError:
                # Ids not shaped like Trello's are never put in a URL; the link stays.
                return None

        return await copy_files(ctx, item.draft.attachments, download)

    async def _snapshot(self, db: AsyncSession, session: ExternalImportSession) -> None:
        if not session.source_ref:
            raise ImportSourceDataError(NO_BOARD_REF)
        creds = await load_credentials(db, session.org_id)
        # No transaction stays open while Trello answers.
        await db.commit()
        self._client = self._client or trello_client.new_client(creds)
        raw = await fetch_snapshot(self._client, session.source_ref)
        self._export = await asyncio.to_thread(parse_board, raw)
        session.storage_path = await store_source_file(
            session.org_id,
            session.id,
            SNAPSHOT_FILENAME,
            compact_json(self._export),
            max_bytes=settings.boards.import_max_snapshot_bytes,
        )

    async def _read(self, session: ExternalImportSession) -> TrelloExport:
        if self._export is None:
            if not session.storage_path:
                raise ImportSourceDataError(NO_SOURCE_FILE)
            data = await load_source_file(session.storage_path)
            self._export = await asyncio.to_thread(load_compact, data)
        return self._export
