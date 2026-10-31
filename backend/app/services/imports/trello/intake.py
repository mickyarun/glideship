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

"""Starting a Trello import: from an uploaded export, or a board picked over the API.

Either way a session is created and the parse job queued (202). An upload
is checked before it's stored: size, a ``.json`` name, and JSON shaped
like a Trello board. Nothing in it is fetched.
"""

import asyncio

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.external_import import (
    ExternalImportSession,
    ExternalImportStatus,
    ImportMode,
    ImportSourceKind,
)
from app.repositories.external_import import ExternalImportSessionRepository
from app.schemas.boards.imports import ImportAccepted, TrelloApiImportCreate, TrelloBoardOption
from app.services.boards.access import BoardCaller
from app.services.boards.errors import BoardRuleError, BoardTooLargeError
from app.services.imports.sessions import queue_discovery
from app.services.imports.storage import store_source_file
from app.services.imports.target import check_may_import
from app.services.imports.trello import client as trello_client
from app.services.imports.trello.constants import SNAPSHOT_FILENAME
from app.services.imports.trello.credentials import load_credentials
from app.services.imports.trello.parse import parse_export
from app.services.upload_policy import UploadPolicyError, import_file_policy

TOO_LARGE = "The export is larger than the {mb} MB import limit."


async def create_from_upload(
    db: AsyncSession, caller: BoardCaller, filename: str | None, data: bytes
) -> ImportAccepted:
    """A session for an uploaded board export (read one byte past the cap)."""
    await check_may_import(db, caller)
    rules = import_file_policy(max_bytes=settings.boards.import_max_upload_bytes)
    if len(data) > rules.max_bytes:
        raise BoardTooLargeError(TOO_LARGE.format(mb=rules.max_mb))
    try:
        rules.resolve_mime(filename or "")
    except UploadPolicyError as exc:
        raise BoardRuleError(str(exc)) from exc
    await asyncio.to_thread(parse_export, data)
    session = await _new_session(db, caller, ImportMode.UPLOAD)
    session.storage_path = await store_source_file(
        caller.org_id, session.id, SNAPSHOT_FILENAME, data
    )
    return await queue_discovery(db, caller, session)


async def create_from_api(
    db: AsyncSession, caller: BoardCaller, body: TrelloApiImportCreate
) -> ImportAccepted:
    """A session that fetches the board from the Trello API in its parse job."""
    await check_may_import(db, caller)
    await load_credentials(db, caller.org_id)
    session = await _new_session(db, caller, ImportMode.API, source_ref=body.trello_board_id)
    return await queue_discovery(db, caller, session)


async def list_trello_boards(db: AsyncSession, caller: BoardCaller) -> list[TrelloBoardOption]:
    """The connected Trello member's open boards, for API mode's picker."""
    await check_may_import(db, caller)
    client = trello_client.new_client(await load_credentials(db, caller.org_id))
    try:
        boards = await client.boards()
    finally:
        await client.aclose()
    return [
        TrelloBoardOption(
            id=b["id"],
            name=b["name"] if isinstance(b.get("name"), str) else "",
            url=b["url"] if isinstance(b.get("url"), str) else None,
        )
        for b in boards
        if isinstance(b.get("id"), str)
    ]


async def _new_session(
    db: AsyncSession, caller: BoardCaller, mode: ImportMode, *, source_ref: str | None = None
) -> ExternalImportSession:
    session = ExternalImportSession(
        org_id=caller.org_id,
        source_kind=ImportSourceKind.TRELLO,
        mode=mode,
        status=ExternalImportStatus.PENDING,
        source_ref=source_ref,
        created_by=caller.user_id,
    )
    return await ExternalImportSessionRepository(db, org_id=caller.org_id).create(session)
