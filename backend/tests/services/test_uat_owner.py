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

"""The org-level UAT owner: settings, role chains, assignment lookup and estimation."""

from __future__ import annotations

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.models.user import UserRole
from app.schemas.settings import BUDStageSettings, UATOwner
from app.services import phase_owner
from app.services.capacity_provider import RoleLoad, phase_capacity
from app.services.estimation_gates import REVIEW_GATE, gate_turnaround_days
from app.services.org_settings import get_role_chains
from app.services.phase_roles import PHASE_ROLE_CHAIN, role_chains

QA_CONFIG = {"bud_stages": {"uat_enabled": True, "uat_owner": "qa"}}


def test_default_owner_is_pm_and_matches_static_map() -> None:
    assert BUDStageSettings().uat_owner is UATOwner.PM
    assert role_chains() == PHASE_ROLE_CHAIN
    assert get_role_chains(None)["uat"] == (UserRole.PM, UserRole.MANAGER)


def test_qa_owner_puts_qa_first_then_pm_and_manager_and_leaves_other_phases() -> None:
    chains = get_role_chains(QA_CONFIG)
    assert chains["uat"] == (UserRole.QA, UserRole.PM, UserRole.MANAGER)
    assert {k: v for k, v in chains.items() if k != "uat"} == {
        k: v for k, v in PHASE_ROLE_CHAIN.items() if k != "uat"
    }


def test_setting_accepts_alias_and_stores_plain_value() -> None:
    saved = BUDStageSettings.model_validate({"uatEnabled": True, "uatOwner": "qa"}).model_dump(
        mode="json"
    )
    assert saved == {"uat_enabled": True, "uat_owner": "qa"}


def test_unknown_owner_is_rejected() -> None:
    with pytest.raises(ValueError):
        BUDStageSettings.model_validate({"uatOwner": "designer"})


@pytest.mark.asyncio
async def test_fixed_phases_never_load_the_org(monkeypatch: pytest.MonkeyPatch) -> None:
    repo = MagicMock(side_effect=AssertionError("org must not be loaded"))
    monkeypatch.setattr(phase_owner, "OrganizationRepository", repo)
    chain = await phase_owner.role_chain_for_phase(MagicMock(), uuid.uuid4(), "testing")
    assert chain == (UserRole.QA, UserRole.DEVELOPER)


@pytest.mark.asyncio
async def test_uat_chain_follows_the_org_setting(monkeypatch: pytest.MonkeyPatch) -> None:
    org = SimpleNamespace(config=QA_CONFIG)
    monkeypatch.setattr(
        phase_owner,
        "OrganizationRepository",
        MagicMock(return_value=MagicMock(get_by_id=AsyncMock(return_value=org))),
    )
    chain = await phase_owner.role_chain_for_phase(MagicMock(), uuid.uuid4(), "uat")
    assert chain == (UserRole.QA, UserRole.PM, UserRole.MANAGER)


@pytest.mark.asyncio
async def test_missing_org_falls_back_to_the_pm_chain(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        phase_owner,
        "OrganizationRepository",
        MagicMock(return_value=MagicMock(get_by_id=AsyncMock(return_value=None))),
    )
    chain = await phase_owner.role_chain_for_phase(MagicMock(), uuid.uuid4(), "uat")
    assert chain == (UserRole.PM, UserRole.MANAGER)


@pytest.mark.asyncio
@pytest.mark.parametrize(("config", "expected"), [(QA_CONFIG, True), ({}, False), (None, False)])
async def test_uat_owner_is_qa_follows_the_setting(
    monkeypatch: pytest.MonkeyPatch, config: dict[str, object] | None, expected: bool
) -> None:
    org = None if config is None else SimpleNamespace(config=config)
    monkeypatch.setattr(
        phase_owner,
        "OrganizationRepository",
        MagicMock(return_value=MagicMock(get_by_id=AsyncMock(return_value=org))),
    )
    assert await phase_owner.uat_owner_is_qa(MagicMock(), uuid.uuid4()) is expected


def test_uat_estimates_use_the_owner_roles_load() -> None:
    loads = {
        UserRole.PM: RoleLoad(pool=1, active=6),
        UserRole.QA: RoleLoad(pool=3, active=0),
    }
    qa_chains = role_chains(UATOwner.QA)
    # Pool sums the chain (QA + PM); active load is the primary role's (QA).
    assert phase_capacity(loads, "uat", qa_chains) == 1.0
    assert gate_turnaround_days(loads, "uat", qa_chains) == REVIEW_GATE.base
    # The PM default still reads the PM backlog of six.
    assert gate_turnaround_days(loads, "uat", PHASE_ROLE_CHAIN) == pytest.approx(
        min(REVIEW_GATE.cap, REVIEW_GATE.base + REVIEW_GATE.penalty_per_backlog * 6)
    )
