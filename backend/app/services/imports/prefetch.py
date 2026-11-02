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


"""Files a batch fetched from the source before it took its locks, and their cleanup.

A source fetches inside :func:`prefetched`. The batch marks each item whose
card it wrote with :meth:`Prefetched.keep`, drops the rest with
:meth:`Prefetched.release_unkept` (they failed, or another session
imported them first: their files are deleted and their bytes go back to
the budget), then commits inside the same block. If anything raised,
including the commit, every file still held is deleted on the way out.
"""

from collections import Counter
from collections.abc import AsyncIterator, Awaitable, Callable, Sequence
from contextlib import asynccontextmanager
from dataclasses import dataclass, field

import structlog

from app.services.attachment_upload import StoredFile
from app.services.file_storage import FileStorageError, get_file_storage
from app.services.imports.context import ImportContext
from app.services.imports.items import ExternalItem

logger = structlog.get_logger(__name__)


@dataclass
class FetchedItem:
    """What one item brought from outside: stored copies by attachment id, and what didn't fit."""

    files: dict[str, StoredFile] = field(default_factory=dict)
    dropped: Counter[str] = field(default_factory=Counter)


class Prefetched:
    """The batch's fetched items, and which of them ended up on a card."""

    def __init__(self) -> None:
        self.items: dict[str, FetchedItem] = {}
        self._kept: set[str] = set()

    def get(self, external_id: str) -> FetchedItem:
        """What was fetched for the item (nothing, when the source fetches nothing)."""
        return self.items.get(external_id) or FetchedItem()

    def keep(self, external_id: str) -> None:
        """The item's card was written; its files stay if the batch commits."""
        self._kept.add(external_id)

    async def release_unkept(self, ctx: ImportContext) -> None:
        """Delete the files of items whose card wasn't written, before the commit."""
        unkept = [i for i in self.items if i not in self._kept]
        await remove_files(ctx, [c for i in unkept for c in self.items.pop(i).files.values()])

    def held_files(self) -> list[StoredFile]:
        """Every copy still held."""
        return [copy for fetched in self.items.values() for copy in fetched.files.values()]


Fetch = Callable[[ExternalItem], Awaitable[FetchedItem]]


@asynccontextmanager
async def prefetched(
    ctx: ImportContext, items: Sequence[ExternalItem], fetch: Fetch
) -> AsyncIterator[Prefetched]:
    """Fetch for every item and yield; if the block raises, delete every file still held."""
    held = Prefetched()
    finished = False
    try:
        for item in items:
            held.items[item.external_id] = await fetch(item)
        yield held
        finished = True
    finally:
        if not finished:
            await remove_files(ctx, held.held_files())


async def remove_files(ctx: ImportContext, files: Sequence[StoredFile]) -> None:
    """Delete copies no card holds and give their bytes back to the budget."""
    storage = get_file_storage()
    for copy in files:
        ctx.budget.refund(copy.size_bytes)
        try:
            await storage.delete(copy.storage_path)
        except FileStorageError as exc:
            logger.error("import_file_orphaned", storage_path=copy.storage_path, error=str(exc))
