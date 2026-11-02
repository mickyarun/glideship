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

A source turns its data into card drafts and labels
(:mod:`app.services.imports.draft`); everything after that (the board
plan, the batches, the card writer, the item maps) is shared. The pipeline
uses a source as an async context manager, one per job, so it can hold a
network client and cache what it loaded. It calls, in order:

- :meth:`ImportSource.check_startable` before any job is queued or run;
- :meth:`~ImportSource.discover` in the parse job;
- :meth:`~ImportSource.load` once per import run, then per batch
  :meth:`~ImportSource.prefetch` (network work, with no transaction open
  and no locks held) around the batch's writes and commit.

This framework imports *cards into one board*. Imports that land somewhere
else (Jira issues becoming BUDs, say) don't fit it and keep their own
pipeline.
"""

from collections.abc import Sequence
from contextlib import AbstractAsyncContextManager
from dataclasses import dataclass
from types import TracebackType
from typing import Any, Protocol, Self

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.external_import import ExternalImportSession, ImportSourceKind
from app.services.boards.access import BoardCaller
from app.services.imports.context import ImportContext
from app.services.imports.draft import SourceBoard
from app.services.imports.items import ExternalItem
from app.services.imports.prefetch import Prefetched


@dataclass(frozen=True)
class ImportDiscovery:
    """What the parse found: how many items, and the source's summary as JSON."""

    total_items: int
    summary: dict[str, Any]


@dataclass(frozen=True)
class MappingIds:
    """The source ids a reviewed mapping may name: every group exactly once, members at most."""

    groups: frozenset[str]
    members: frozenset[str]


class ImportSource(Protocol):
    """One kind of source, such as a Trello board."""

    kind: ImportSourceKind

    async def __aenter__(self) -> Self:
        """Ready the source for one job."""
        ...

    async def __aexit__(
        self, kind: type[BaseException] | None, exc: BaseException | None, tb: TracebackType | None
    ) -> None:
        """Release network clients."""
        ...

    async def check_startable(
        self, db: AsyncSession, session: ExternalImportSession, caller: BoardCaller
    ) -> None:
        """Refuse a parse or a run this caller can't start (rights, credentials)."""
        ...

    def mapping_ids(self, discovery: dict[str, Any]) -> MappingIds:
        """The ids in a stored discovery that a mapping is checked against."""
        ...

    async def discover(self, db: AsyncSession, session: ExternalImportSession) -> ImportDiscovery:
        """Read the source data (fetching it first in API mode) and summarise it."""
        ...

    async def load(self, db: AsyncSession, session: ExternalImportSession) -> SourceBoard:
        """The stored source as card drafts in a stable order, and its labels."""
        ...

    def prefetch(
        self, items: Sequence[ExternalItem], ctx: ImportContext
    ) -> AbstractAsyncContextManager[Prefetched]:
        """Fetch what ``items`` need from outside; see :func:`app.services.imports.prefetch`."""
        ...
