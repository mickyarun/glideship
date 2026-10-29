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

"""The upload steps every attachment surface shares, in the order that matters.

1. :func:`precheck` before the body is read: the per-parent file count, a
   safe filename that fits the column, and the type from its extension.
2. :func:`store` once the body is read (one byte past the cap): size,
   emptiness, then the bytes go to :class:`FileStorage`.

Each refusal is an :class:`UploadRejectedError` naming the problem, so a
route maps problems to its own statuses. Storage failures are logged and
reported with a generic message; the backend's detail never reaches a client.
"""

import uuid
from dataclasses import dataclass
from enum import StrEnum

import structlog

from app.core.paths import sanitize_filename
from app.models.thread_columns import ATTACHMENT_FILENAME_LENGTH
from app.services.file_storage import FileStorage, FileStorageError
from app.services.upload_policy import UploadPolicy, UploadPolicyError

logger = structlog.get_logger(__name__)

STORAGE_FAILED = "The file couldn't be stored. Try again."
# The random prefix put before the filename in the storage path.
_PREFIX_LENGTH = 12
# The stored name is one path component, which most filesystems cap at 255
# bytes; leave room for the prefix and a temporary suffix while writing.
FILENAME_MAX = min(ATTACHMENT_FILENAME_LENGTH, 200)


class UploadProblem(StrEnum):
    """Why an upload was refused."""

    COUNT = "count"
    TYPE = "type"
    SIZE = "size"
    EMPTY = "empty"
    STORAGE = "storage"


class UploadRejectedError(Exception):
    """An upload was refused; the message is written for the uploader."""

    def __init__(self, problem: UploadProblem, message: str) -> None:
        super().__init__(message)
        self.problem = problem


@dataclass(frozen=True)
class CheckedName:
    """A filename that passed :func:`precheck`, with its canonical type."""

    filename: str
    mime_type: str


@dataclass(frozen=True)
class StoredFile:
    """A file now held in storage, ready to be recorded on its parent."""

    filename: str
    mime_type: str
    size_bytes: int
    storage_path: str


def fit_filename(name: str, limit: int = FILENAME_MAX) -> str:
    """Shorten the stem so ``name`` fits ``limit`` characters, keeping the extension."""
    if len(name) <= limit:
        return name
    stem, dot, ext = name.rpartition(".")
    if not dot:
        return name[:limit]
    return f"{stem[: limit - len(ext) - 1]}.{ext}"


def precheck(policy: UploadPolicy, filename: str | None, existing: int) -> CheckedName:
    """The checks that need no bytes: the count, the name and the type."""
    try:
        policy.check_count(existing)
    except UploadPolicyError as exc:
        raise UploadRejectedError(UploadProblem.COUNT, str(exc)) from exc
    safe = fit_filename(sanitize_filename(filename, fallback="attachment"))
    try:
        mime = policy.resolve_mime(safe)
    except UploadPolicyError as exc:
        raise UploadRejectedError(UploadProblem.TYPE, str(exc)) from exc
    return CheckedName(filename=safe, mime_type=mime)


async def store(
    policy: UploadPolicy,
    storage: FileStorage,
    *,
    org_id: uuid.UUID,
    folder: str,
    name: CheckedName,
    data: bytes,
) -> StoredFile:
    """Check the bytes and put them under ``{org}/{folder}/{random}-{name}``.

    The random prefix keeps two files of the same name on one parent apart.
    """
    if len(data) > policy.max_bytes:
        raise UploadRejectedError(
            UploadProblem.SIZE, f"{policy.label} exceeds the {policy.max_mb} MB limit."
        )
    if not data:
        raise UploadRejectedError(UploadProblem.EMPTY, f"{name.filename} is empty.")
    relative = f"{folder}/{uuid.uuid4().hex[:_PREFIX_LENGTH]}-{name.filename}"
    try:
        path = await storage.upload(
            org_id=str(org_id),
            relative_path=relative,
            data=data,
            content_type=name.mime_type,
            policy=policy,
        )
    except FileStorageError as exc:
        logger.error("attachment_store_failed", folder=folder, error=str(exc))
        raise UploadRejectedError(UploadProblem.STORAGE, STORAGE_FAILED) from exc
    return StoredFile(
        filename=name.filename,
        mime_type=name.mime_type,
        size_bytes=len(data),
        storage_path=path,
    )
