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

"""Imports from other tools into boards: one session per run, one map row per item.

Both tables are keyed by a source enum, so Trello is the first source and
others add a value. ``external_item_maps`` is what makes a re-import
idempotent: an item already imported into a board is skipped, while the
same source board can still be imported into a second board.
"""

import uuid
from enum import StrEnum
from typing import Any

from sqlalchemy import ForeignKey, ForeignKeyConstraint, Index, Integer, String, Text, text
from sqlalchemy import UniqueConstraint as Unique
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel
from app.models.board_enums import pg_enum

EXTERNAL_ID_LENGTH = 64
STORAGE_PATH_LENGTH = 1000
JOB_ID_LENGTH = 100


class ImportSourceKind(StrEnum):
    """Where an import reads from."""

    TRELLO = "trello"


class ImportMode(StrEnum):
    """How the source data arrives: an uploaded export, or the source's API."""

    UPLOAD = "upload"
    API = "api"


class ExternalImportStatus(StrEnum):
    """Where one import session stands."""

    PENDING = "pending"
    PARSING = "parsing"
    READY = "ready"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


# A server restart leaves these sessions with no job behind them.
IN_FLIGHT_IMPORT_STATUSES = frozenset({ExternalImportStatus.PARSING, ExternalImportStatus.RUNNING})


class ExternalItemStatus(StrEnum):
    """What happened to one source item."""

    IMPORTED = "imported"
    SKIPPED = "skipped"
    FAILED = "failed"


class ExternalImportSession(BaseModel):
    """One import run: the stored source data, its summary, the mapping and progress.

    ``board_id`` is the target board, set once the mapping names it (or the
    import creates it). ``last_processed_index`` is the last item whose
    batch committed, so a restarted job resumes after it.
    """

    __tablename__ = "external_import_sessions"
    __table_args__ = (
        # The target board must be in the session's org.
        ForeignKeyConstraint(
            ["board_id", "org_id"],
            ["boards.id", "boards.org_id"],
            name="fk_external_import_sessions_board_org",
        ),
        Index("ix_external_import_sessions_org_status", "org_id", "status"),
        Index("ix_external_import_sessions_org_creator", "org_id", "created_by"),
    )

    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False
    )
    board_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    source_kind: Mapped[ImportSourceKind] = mapped_column(
        pg_enum(ImportSourceKind, "import_source_kind"), nullable=False
    )
    mode: Mapped[ImportMode] = mapped_column(pg_enum(ImportMode, "import_mode"), nullable=False)
    status: Mapped[ExternalImportStatus] = mapped_column(
        pg_enum(ExternalImportStatus, "external_import_status"),
        nullable=False,
        default=ExternalImportStatus.PENDING,
        server_default=ExternalImportStatus.PENDING.value,
    )
    # The source's own id for what is imported (a Trello board id in API mode).
    source_ref: Mapped[str | None] = mapped_column(String(EXTERNAL_ID_LENGTH), nullable=True)
    # The uploaded export, or the snapshot the API fetch saved.
    storage_path: Mapped[str | None] = mapped_column(String(STORAGE_PATH_LENGTH), nullable=True)
    # The reviewed mapping: target board, list → stage, member → user, archived choice.
    config: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    # What the parse found: lists, labels, members, counts and warnings.
    discovery: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    # What the run did: per-status counts and what was dropped on the way.
    result: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    total_cards: Mapped[int | None] = mapped_column(Integer, nullable=True)
    processed_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )
    last_processed_index: Mapped[int | None] = mapped_column(Integer, nullable=True)
    job_id: Mapped[str | None] = mapped_column(String(JOB_ID_LENGTH), nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    def __repr__(self) -> str:
        return (
            f"<ExternalImportSession(kind={self.source_kind.value}, "
            f"status={self.status.value}, done={self.processed_count}/{self.total_cards})>"
        )


class ExternalItemMap(BaseModel):
    """One source item and the card it became (or why it didn't)."""

    __tablename__ = "external_item_maps"
    __table_args__ = (
        Unique(
            "org_id",
            "source_kind",
            "external_id",
            "target_board_id",
            name="uq_external_item_maps_org_kind_item_board",
        ),
        ForeignKeyConstraint(
            ["target_board_id", "org_id"],
            ["boards.id", "boards.org_id"],
            ondelete="CASCADE",
            name="fk_external_item_maps_board_org",
        ),
        Index("ix_external_item_maps_session_status", "session_id", "status"),
    )

    org_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("external_import_sessions.id", ondelete="CASCADE"),
        nullable=False,
    )
    source_kind: Mapped[ImportSourceKind] = mapped_column(
        pg_enum(ImportSourceKind, "import_source_kind"), nullable=False
    )
    external_id: Mapped[str] = mapped_column(String(EXTERNAL_ID_LENGTH), nullable=False)
    target_board_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    card_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("board_cards.id", ondelete="SET NULL"), nullable=True
    )
    status: Mapped[ExternalItemStatus] = mapped_column(
        pg_enum(ExternalItemStatus, "external_item_status"), nullable=False
    )
    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    def __repr__(self) -> str:
        return f"<ExternalItemMap(external_id={self.external_id!r}, status={self.status.value})>"
