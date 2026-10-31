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


"""Board imports: create a session from a source, review its mapping, start it.

Sessions are generic (``/imports/{id}``, its ``mapping`` and ``start``);
creating one is per source (``/imports/trello/upload`` and
``/imports/trello/api``). ``imports`` is a reserved board key, so these
fixed paths never collide with ``/{key}``. Who may import into which board
is checked in the services: before an upload is read, when the mapping is
saved, and again when the import starts and runs.
"""

import uuid

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.datastructures import UploadFile

from app.config import settings
from app.core.board_deps import board_caller
from app.core.deps import get_db
from app.schemas.boards.import_mapping import ImportMapping
from app.schemas.boards.imports import (
    ImportAccepted,
    ImportSessionRead,
    TrelloApiImportCreate,
    TrelloBoardOption,
)
from app.services.boards.access import BoardCaller
from app.services.boards.errors import BoardRuleError
from app.services.imports import admission, review, sessions
from app.services.imports.session_read import session_read
from app.services.imports.trello import intake

router = APIRouter(tags=["boards"])

IMPORTS = "/imports"
TRELLO = f"{IMPORTS}/trello"
NO_FILE = "Attach the Trello board export as the 'file' field."
UPLOAD_BODY = {
    "requestBody": {
        "content": {
            "multipart/form-data": {
                "schema": {
                    "type": "object",
                    "properties": {"file": {"type": "string", "format": "binary"}},
                    "required": ["file"],
                }
            }
        }
    }
}


@router.post(
    f"{TRELLO}/upload",
    response_model=ImportAccepted,
    status_code=status.HTTP_202_ACCEPTED,
    openapi_extra=UPLOAD_BODY,
)
async def upload_trello_export(
    request: Request,
    caller: BoardCaller = Depends(board_caller),
    db: AsyncSession = Depends(get_db),
) -> ImportAccepted:
    """Upload a board export (multipart ``file``); it's parsed in the job this returns."""
    admitted = await admission.admit(db, caller)
    form = await request.form(max_files=1)
    try:
        upload = form.get("file")
        if not isinstance(upload, UploadFile):
            raise BoardRuleError(NO_FILE)
        data = await upload.read(settings.boards.import_max_upload_bytes + 1)
        return await intake.create_from_upload(db, admitted, upload.filename, data)
    finally:
        await form.close()


@router.post(f"{TRELLO}/api", response_model=ImportAccepted, status_code=status.HTTP_202_ACCEPTED)
async def import_trello_board(
    body: TrelloApiImportCreate,
    caller: BoardCaller = Depends(board_caller),
    db: AsyncSession = Depends(get_db),
) -> ImportAccepted:
    """Import a board over the Trello API with the org's token; it's fetched in the job."""
    return await intake.create_from_api(db, await intake.admit_api(db, caller), body)


@router.get(f"{TRELLO}/boards", response_model=list[TrelloBoardOption])
async def list_trello_boards(
    caller: BoardCaller = Depends(board_caller), db: AsyncSession = Depends(get_db)
) -> list[TrelloBoardOption]:
    """The connected Trello member's boards, for API mode."""
    return await intake.list_trello_boards(db, caller)


@router.get(f"{IMPORTS}/{{session_id}}", response_model=ImportSessionRead)
async def get_import(
    session_id: uuid.UUID,
    caller: BoardCaller = Depends(board_caller),
    db: AsyncSession = Depends(get_db),
) -> ImportSessionRead:
    """The session: status, what the parse found, the saved mapping and the result."""
    return await session_read(db, await sessions.get_session(db, caller, session_id))


@router.put(f"{IMPORTS}/{{session_id}}/mapping", response_model=ImportSessionRead)
async def save_mapping(
    session_id: uuid.UUID,
    body: ImportMapping,
    caller: BoardCaller = Depends(board_caller),
    db: AsyncSession = Depends(get_db),
) -> ImportSessionRead:
    """Save the reviewed mapping: target board, group → stage, member → person, archived cards."""
    session = await sessions.get_session(db, caller, session_id)
    await review.save_mapping(db, caller, session, body)
    return await session_read(db, session)


@router.post(
    f"{IMPORTS}/{{session_id}}/start",
    response_model=ImportAccepted,
    status_code=status.HTTP_202_ACCEPTED,
)
async def start_import(
    session_id: uuid.UUID,
    caller: BoardCaller = Depends(board_caller),
    db: AsyncSession = Depends(get_db),
) -> ImportAccepted:
    """Start the import, resume one that failed part-way, or read a board whose parse failed."""
    return await sessions.start_import(db, caller, session_id)
