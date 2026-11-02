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

"""Helpers for the import tests: local storage, captured jobs run by hand, mappings."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import select, update

from app.models.board_card import BoardCard
from app.models.external_import import ExternalImportSession
from app.models.user import User
from app.services.file_storage import FileStorage
from app.services.imports import files, pipeline, prefetch, queueing, storage
from app.services.imports.job_payload import ImportJobPayload
from app.services.job_queue import JOB_IMPORT_DISCOVER, JOB_IMPORT_RUN
from tests.integration.board_api_support import BOARDS, Person, ok, person, use_local_storage
from tests.integration.scan_features_bugs_support import Factory
from tests.services.trello_fixture import (
    BACKLOG,
    DOING,
    DONE,
    OLD,
    PRIYA,
    SAM,
    fixture_bytes,
)

IMPORTS = f"{BOARDS}/imports"
TRELLO_UPLOAD = f"{IMPORTS}/trello/upload"
TRELLO_API = f"{IMPORTS}/trello/api"


@dataclass
class Jobs:
    """Jobs the API queued, run by hand on the test database."""

    factory: Factory
    queued: list[tuple[str, str, dict[str, Any]]] = field(default_factory=list)

    async def run_all(self) -> None:
        """Run every queued job in order, emptying the queue."""
        while self.queued:
            job_id, job_type, payload = self.queued.pop(0)
            async with self.factory() as db:
                body = ImportJobPayload.model_validate(payload)
                if job_type == JOB_IMPORT_DISCOVER:
                    await pipeline.run_discovery(db, body, job_id)
                else:
                    assert job_type == JOB_IMPORT_RUN
                    await pipeline.run_import(db, body, job_id)


def capture_jobs(factory: Factory, monkeypatch: pytest.MonkeyPatch) -> Jobs:
    """Queue import jobs in a list instead of the in-memory job queue."""
    jobs = Jobs(factory)

    def _queue(job_id: str, job_type: str, *, payload: dict[str, Any], user_id: str) -> None:
        jobs.queued.append((job_id, job_type, payload))

    monkeypatch.setattr(queueing, "create_job_with_id", _queue)
    return jobs


def use_import_storage(root: Path, monkeypatch: pytest.MonkeyPatch) -> FileStorage:
    """Import files and card attachments in a local directory."""
    local = use_local_storage(root, monkeypatch)
    for module in (storage, files, prefetch):
        monkeypatch.setattr(module, "get_file_storage", lambda: local)
    return local


async def named(
    factory: Factory, org: uuid.UUID, name: str, role: str | None = "developer"
) -> Person:
    """A member with this full name (names are what member suggestions match)."""
    who = await person(factory, org, role)
    async with factory() as db:
        await db.execute(update(User).where(User.id == who.id).values(name=name))
        await db.commit()
    return who


async def upload(
    client: AsyncClient, who: Person, data: bytes | None = None, name: str = "board.json"
) -> Any:
    """POST an export; returns the raw response."""
    content = fixture_bytes() if data is None else data
    files_field = {"file": (name, content, "application/json")}
    return await client.post(TRELLO_UPLOAD, files=files_field, headers=who.headers)


async def parsed(client: AsyncClient, who: Person, jobs: Jobs) -> str:
    """Upload the fixture and run its parse job; returns the session id."""
    accepted = ok(await upload(client, who), 202)
    await jobs.run_all()
    return str(accepted["sessionId"])


def mapping(
    target: dict[str, Any],
    *,
    groups: list[dict[str, Any]] | None = None,
    priya: uuid.UUID | None = None,
    archived: str = "archive",
) -> dict[str, Any]:
    """The fixture's lists as new stages (old list skipped), Priya mapped when given."""
    default_groups = [
        {"group_id": BACKLOG, "action": "new", "name": "Backlog", "category": "todo"},
        {"group_id": DOING, "action": "new", "name": "Doing", "category": "in_progress"},
        {"group_id": DONE, "action": "new", "name": "Done", "category": "done"},
        {"group_id": OLD, "action": "skip"},
    ]
    members = [{"member_id": PRIYA, "user_id": str(priya) if priya else None}]
    members.append({"member_id": SAM, "user_id": None})
    return {
        "target": target,
        "groups": default_groups if groups is None else groups,
        "members": members,
        "archived_cards": archived,
    }


def new_board(key: str, **extra: Any) -> dict[str, Any]:
    """A new-board target."""
    return {"kind": "new", "name": f"Imported {key}", "key": key, **extra}


async def save_and_start(
    client: AsyncClient, who: Person, session_id: str, body: dict[str, Any]
) -> dict[str, Any]:
    """Save the mapping and start the import (not yet run)."""
    ok(await client.put(f"{IMPORTS}/{session_id}/mapping", json=body, headers=who.headers))
    return ok(await client.post(f"{IMPORTS}/{session_id}/start", headers=who.headers), 202)


def start_url(session_id: str) -> str:
    """Where a session is started (or resumed, or read again)."""
    return f"{IMPORTS}/{session_id}/start"


async def session_row(factory: Factory, session_id: str | uuid.UUID) -> ExternalImportSession:
    """The session as stored."""
    async with factory() as db:
        found = await db.get(ExternalImportSession, uuid.UUID(str(session_id)))
        assert found is not None
        return found


async def board_cards(factory: Factory, board_id: str | uuid.UUID) -> list[BoardCard]:
    """The board's cards, by number."""
    async with factory() as db:
        rows = await db.scalars(
            select(BoardCard)
            .where(BoardCard.board_id == uuid.UUID(str(board_id)))
            .order_by(BoardCard.number)
        )
        return list(rows)
