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

"""Trello imports: upload or pick a board, review the mapping, start, follow the job.

``imports`` is a reserved board key, so these fixed paths never collide
with ``/{key}``. Who may import into which board is checked in the
services, when the mapping is saved and again when the import starts.
"""

import uuid
from typing import Any

from fastapi import APIRouter, Depends, Request, status
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError
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
from app.services.imports import sessions
from app.services.imports.trello import intake, review

router = APIRouter(tags=["boards"])

TRELLO = "/imports/trello"
MULTIPART = "multipart/form-data"
NO_FILE = "Attach the Trello board export as the 'file' field."


@router.post(
    TRELLO,
    response_model=ImportAccepted,
    status_code=status.HTTP_202_ACCEPTED,
    openapi_extra={
        "requestBody": {
            "content": {
                MULTIPART: {
                    "schema": {
                        "type": "object",
                        "properties": {"file": {"type": "string", "format": "binary"}},
                    }
                },
                "application/json": {"schema": TrelloApiImportCreate.model_json_schema()},
            }
        }
    },
)
async def create_import(
    request: Request,
    caller: BoardCaller = Depends(board_caller),
    db: AsyncSession = Depends(get_db),
) -> ImportAccepted:
    """Upload a board export (multipart ``file``), or send ``{mode: "api", trello_board_id}``."""
    if request.headers.get("content-type", "").startswith(MULTIPART):
        form = await request.form(max_files=1)
        upload = form.get("file")
        if not isinstance(upload, UploadFile):
            raise BoardRuleError(NO_FILE)
        data = await upload.read(settings.boards.import_max_upload_bytes + 1)
        return await intake.create_from_upload(db, caller, upload.filename, data)
    return await intake.create_from_api(db, caller, _api_body(await _json(request)))


@router.get(f"{TRELLO}/boards", response_model=list[TrelloBoardOption])
async def list_trello_boards(
    caller: BoardCaller = Depends(board_caller), db: AsyncSession = Depends(get_db)
) -> list[TrelloBoardOption]:
    """The connected Trello member's boards, for API mode."""
    return await intake.list_trello_boards(db, caller)


@router.get(f"{TRELLO}/{{session_id}}", response_model=ImportSessionRead)
async def get_import(
    session_id: uuid.UUID,
    caller: BoardCaller = Depends(board_caller),
    db: AsyncSession = Depends(get_db),
) -> ImportSessionRead:
    """The session: status, what the parse found, the saved mapping and the result."""
    return await sessions.session_read(db, await sessions.get_session(db, caller, session_id))


@router.put(f"{TRELLO}/{{session_id}}/mapping", response_model=ImportSessionRead)
async def save_mapping(
    session_id: uuid.UUID,
    body: ImportMapping,
    caller: BoardCaller = Depends(board_caller),
    db: AsyncSession = Depends(get_db),
) -> ImportSessionRead:
    """Save the reviewed mapping: target board, list → stage, member → person, archived cards."""
    session = await sessions.get_session(db, caller, session_id)
    await review.save_mapping(db, caller, session, body)
    return await sessions.session_read(db, session)


@router.post(
    f"{TRELLO}/{{session_id}}/start",
    response_model=ImportAccepted,
    status_code=status.HTTP_202_ACCEPTED,
)
async def start_import(
    session_id: uuid.UUID,
    caller: BoardCaller = Depends(board_caller),
    db: AsyncSession = Depends(get_db),
) -> ImportAccepted:
    """Start the import, or resume one that failed part-way."""
    return await sessions.start_import(db, caller, session_id)


async def _json(request: Request) -> Any:
    try:
        return await request.json()
    except ValueError as exc:
        raise RequestValidationError(
            [{"type": "json_invalid", "loc": ("body",), "msg": str(exc)}]
        ) from exc


def _api_body(raw: Any) -> TrelloApiImportCreate:
    try:
        return TrelloApiImportCreate.model_validate(raw)
    except ValidationError as exc:
        raise RequestValidationError(exc.errors()) from exc
