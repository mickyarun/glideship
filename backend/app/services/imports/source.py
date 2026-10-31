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

"""What every import source provides to the shared pipeline.

The pipeline calls, in order: :meth:`ImportSource.discover` (the parse
job), then for the import job :meth:`~ImportSource.prepare` once,
:meth:`~ImportSource.iter_items` for the items in a stable order, and per
batch :meth:`~ImportSource.prefetch` (network work, no locks held) and
:meth:`~ImportSource.write_item` (database work inside the batch).
A source instance serves one job, so it may cache what it loaded.
"""

import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any, Protocol

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.external_import import ExternalImportSession, ImportSourceKind
from app.services.imports.context import ImportContext


@dataclass(frozen=True)
class ExternalItem:
    """One source item, in source order.

    ``index`` is stable across runs of the same session, which is what
    ``last_processed_index`` resumes from. ``skip_reason`` is set when the
    mapping leaves the item out. ``payload`` is the source's own draft.
    """

    index: int
    external_id: str
    payload: Any
    skip_reason: str | None = None


@dataclass(frozen=True)
class ImportDiscovery:
    """What the parse found: how many items, and the source's summary as JSON."""

    total_items: int
    summary: dict[str, Any]


class ImportSource(Protocol):
    """One kind of source, such as a Trello board."""

    kind: ImportSourceKind

    async def discover(self, db: AsyncSession, session: ExternalImportSession) -> ImportDiscovery:
        """Read the source data (fetching it first in API mode) and summarise it."""
        ...

    async def prepare(self, ctx: ImportContext) -> None:
        """Shape the target board for the mapping (stages, labels, members), idempotently."""
        ...

    def iter_items(self, session: ExternalImportSession) -> AsyncIterator[ExternalItem]:
        """Every item in a stable source order."""
        ...

    async def prefetch(self, item: ExternalItem, ctx: ImportContext) -> None:
        """Fetch what the item needs from outside (files) before the batch takes locks."""
        ...

    async def write_item(self, item: ExternalItem, ctx: ImportContext) -> uuid.UUID:
        """Write the item as a card; returns the card id."""
        ...

    async def discard(self, item: ExternalItem) -> None:
        """Remove what :meth:`prefetch` stored for an item that failed to write."""
        ...

    async def close(self) -> None:
        """Release network clients."""
        ...
