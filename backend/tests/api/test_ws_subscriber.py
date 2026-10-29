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

"""A socket's identity: active member, with permissions; the owner holds every one."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from types import SimpleNamespace
from typing import Any

import pytest

from app.api.v1 import ws
from app.core.permission_deps import PermissionSet
from app.core.permissions import ALL_PERMISSION_IDS, WORKSPACE_ENGINEERING

USER, ORG = uuid.uuid4(), uuid.uuid4()


@asynccontextmanager
async def _session() -> AsyncIterator[object]:
    yield object()


def _patch(
    monkeypatch: pytest.MonkeyPatch,
    *,
    active: bool = True,
    member: bool = True,
    perms: PermissionSet | None = None,
) -> None:
    class _Users:
        def __init__(self, _db: object) -> None:
            pass

        async def get_by_id(self, _id: uuid.UUID) -> Any:
            return SimpleNamespace(is_active=active)

        async def is_member_of_org(self, _user: uuid.UUID, _org: uuid.UUID) -> bool:
            return member

    async def _perms(_db: object, _user: uuid.UUID, _org: uuid.UUID) -> PermissionSet | None:
        return perms

    monkeypatch.setattr(ws, "AsyncSessionLocal", _session)
    monkeypatch.setattr(ws, "UserRepository", _Users)
    monkeypatch.setattr(ws, "member_permission_set", _perms)


PAYLOAD = {"sub": str(USER), "org_id": str(ORG)}


async def test_the_owner_holds_every_permission(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch(monkeypatch, perms=PermissionSet(ids=frozenset(), is_owner=True))
    who = await ws._resolve_subscriber(PAYLOAD)
    assert who is not None
    assert who.permissions == frozenset(ALL_PERMISSION_IDS)
    assert who.has_engineering


async def test_a_member_holds_their_roles_permissions(monkeypatch: pytest.MonkeyPatch) -> None:
    ids = frozenset({"boards:view"})
    _patch(monkeypatch, perms=PermissionSet(ids=ids, is_owner=False))
    who = await ws._resolve_subscriber(PAYLOAD)
    assert who is not None
    assert (who.user_id, who.org_id, who.permissions) == (str(USER), str(ORG), ids)
    assert not who.has_engineering
    assert WORKSPACE_ENGINEERING not in who.permissions


@pytest.mark.parametrize(
    ("payload", "flags"),
    [
        (PAYLOAD, {"member": False}),
        (PAYLOAD, {"active": False}),
        (PAYLOAD, {"perms": None}),
        ({"sub": "not-a-uuid", "org_id": str(ORG)}, {}),
    ],
)
async def test_non_members_and_bad_tokens_get_no_subscriber(
    monkeypatch: pytest.MonkeyPatch, payload: dict[str, str], flags: dict[str, Any]
) -> None:
    flags.setdefault("perms", PermissionSet(ids=frozenset(), is_owner=False))
    _patch(monkeypatch, **flags)
    assert await ws._resolve_subscriber(payload) is None
