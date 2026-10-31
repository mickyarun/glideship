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


"""An import session as the review and progress screens read it."""

from typing import Any

from pydantic import TypeAdapter
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.external_import import ExternalImportSession
from app.repositories.board import BoardRepository
from app.schemas.boards.import_mapping import ImportMapping
from app.schemas.boards.imports import ImportDiscoveryRead, ImportResult, ImportSessionRead

_DISCOVERY: TypeAdapter[ImportDiscoveryRead] = TypeAdapter(ImportDiscoveryRead)


async def session_read(db: AsyncSession, session: ExternalImportSession) -> ImportSessionRead:
    """The session with its discovery, mapping and result parsed."""
    board_key = None
    if session.board_id is not None:
        board = await BoardRepository(db, org_id=session.org_id).get_by_id(session.board_id)
        board_key = board.key if board else None
    return ImportSessionRead(
        id=session.id,
        source_kind=session.source_kind,
        mode=session.mode,
        status=session.status,
        board_id=session.board_id,
        board_key=board_key,
        total_cards=session.total_cards,
        processed_count=session.processed_count,
        last_processed_index=session.last_processed_index,
        job_id=session.job_id,
        error=session.error,
        discovery=None if session.discovery is None else _discovery(session),
        mapping=None if session.config is None else ImportMapping.model_validate(session.config),
        result=None if session.result is None else ImportResult.model_validate(session.result),
        created_at=session.created_at,
        updated_at=session.updated_at,
    )


def _discovery(session: ExternalImportSession) -> ImportDiscoveryRead:
    stored: dict[str, Any] = dict(session.discovery or {})
    # The union is told apart by source kind; the session's kind is the truth.
    stored["source_kind"] = session.source_kind.value
    return _DISCOVERY.validate_python(stored)
