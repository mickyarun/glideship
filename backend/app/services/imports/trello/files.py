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

"""Copying a card's uploaded Trello files into our storage (API mode only).

Each file passes the card attachment rules (type, per-file size, files
per card) and the import's byte budget, ``BoardsConfig.import_max_attachment_bytes``.
A file that can't be copied stays on the card as a link instead.
"""

from collections.abc import Iterable

import structlog

from app.services.attachment_upload import StoredFile, UploadRejectedError, precheck, store
from app.services.boards.attachment_rules import policy
from app.services.file_storage import FileStorageError, get_file_storage
from app.services.imports.context import ImportContext
from app.services.imports.errors import ImportSourceDataError
from app.services.imports.trello.cards import AttachmentDraft
from app.services.imports.trello.client import TrelloClient

logger = structlog.get_logger(__name__)


async def fetch_files(
    client: TrelloClient, ctx: ImportContext, card_id: str, attachments: Iterable[AttachmentDraft]
) -> dict[str, StoredFile]:
    """Trello attachment id → the stored copy, for every upload that fits."""
    rules = policy()
    stored: dict[str, StoredFile] = {}
    for attachment in attachments:
        if not attachment.is_upload:
            continue
        try:
            name = precheck(rules, attachment.name, len(stored))
        except UploadRejectedError:
            ctx.counters["files_kept_as_links"] += 1
            continue
        limit = min(rules.max_bytes, ctx.budget.remaining)
        data = await _download(client, card_id, attachment, limit) if limit else None
        if data is None:
            ctx.counters["files_kept_as_links"] += 1
            continue
        try:
            copy = await store(
                rules,
                get_file_storage(),
                org_id=ctx.org_id,
                folder=f"board-attachments/{ctx.board.key}/import-{ctx.session.id}",
                name=name,
                data=data,
            )
        except UploadRejectedError:
            ctx.counters["files_kept_as_links"] += 1
            continue
        ctx.budget.spend(copy.size_bytes)
        stored[attachment.id] = copy
    return stored


async def _download(
    client: TrelloClient, card_id: str, attachment: AttachmentDraft, limit: int
) -> bytes | None:
    try:
        return await client.download(card_id, attachment.id, attachment.name, limit)
    except ImportSourceDataError:
        # Ids not shaped like Trello's are never put in a URL; the link stays.
        return None


async def remove_files(files: Iterable[StoredFile]) -> None:
    """Delete copies whose card was never written."""
    storage = get_file_storage()
    for copy in files:
        try:
            await storage.delete(copy.storage_path)
        except FileStorageError as exc:
            logger.error("import_file_orphaned", storage_path=copy.storage_path, error=str(exc))
