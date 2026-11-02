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


"""Where an import keeps its source file: the parsed board in its compact form.

The file lives from the parse until the run completes, when it's deleted;
the retention sweep removes the files of abandoned sessions.
"""

import uuid

import structlog

from app.services.file_storage import FileStorageError, get_file_storage
from app.services.imports.errors import ImportSourceUnavailableError
from app.services.upload_policy import import_file_policy

logger = structlog.get_logger(__name__)

JSON_TYPE = "application/json"
STORE_FAILED = "The import file couldn't be stored. Try again."


async def store_source_file(
    org_id: uuid.UUID, session_id: uuid.UUID, filename: str, data: bytes, *, max_bytes: int
) -> str:
    """Store the session's source JSON (at most ``max_bytes``); returns its storage path."""
    try:
        return await get_file_storage().upload(
            org_id=str(org_id),
            relative_path=f"imports/{session_id}/{filename}",
            data=data,
            content_type=JSON_TYPE,
            policy=import_file_policy(max_bytes=max_bytes),
        )
    except FileStorageError as exc:
        logger.error("import_file_store_failed", session_id=str(session_id), error=str(exc))
        raise ImportSourceUnavailableError(STORE_FAILED) from exc


async def load_source_file(storage_path: str) -> bytes:
    """The stored source JSON."""
    try:
        data, _ = await get_file_storage().download(storage_path)
    except FileStorageError as exc:
        logger.error("import_file_load_failed", storage_path=storage_path, error=str(exc))
        raise ImportSourceUnavailableError(STORE_FAILED) from exc
    return data


async def delete_source_file(storage_path: str) -> bool:
    """Delete a stored source file; False (and logged) when storage refused."""
    try:
        await get_file_storage().delete(storage_path)
    except FileStorageError as exc:
        logger.error("import_file_delete_failed", storage_path=storage_path, error=str(exc))
        return False
    return True
