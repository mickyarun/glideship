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

"""Every socket scope registers a check, and an unregistered one is refused."""

from __future__ import annotations

from typing import get_args

import pytest

from app.api.v1 import ws_scope_checks
from app.services.ws_topic_policy import Scope, Subscriber

WHO = Subscriber(user_id="u1", org_id="o1", has_engineering=True)


def test_every_scope_has_a_check() -> None:
    assert set(ws_scope_checks.SCOPE_CHECKS) == set(get_args(Scope))


async def test_a_scope_without_a_check_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delitem(ws_scope_checks.SCOPE_CHECKS, "user")
    assert not await ws_scope_checks.passes_scope_check("notifications:u1", WHO)


async def test_string_only_scopes_pass_their_check() -> None:
    for topic in ("notifications:u1", "org:o1", "job:abc"):
        assert await ws_scope_checks.passes_scope_check(topic, WHO)
    assert not await ws_scope_checks.passes_scope_check("nope:x", WHO)
