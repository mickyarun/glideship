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

"""Tests for the phase → role chain map.

These tests exist to catch the silent failure mode where someone adds a
new lifecycle phase to ``estimation_engine.PHASE_ORDER`` and forgets to
extend ``PHASE_ROLE_CHAIN`` — the engine would silently default that
phase's capacity to 1.0 and the forecast would be wrong without anyone
noticing. Keep them strict.
"""

from __future__ import annotations

import pytest

from app.models.user import UserRole
from app.schemas.settings import UATOwner
from app.services.estimation_engine import PHASE_ORDER
from app.services.phase_roles import PHASE_ROLE_CHAIN, role_chains


@pytest.mark.parametrize("owner", list(UATOwner))
def test_every_lifecycle_phase_has_a_role(owner: UATOwner) -> None:
    """Adding a phase to PHASE_ORDER without a role chain would mean
    capacity for that phase silently defaults to 1.0, hiding the
    accuracy regression. The two lists must move together."""
    missing = [p for p in PHASE_ORDER if not role_chains(owner).get(p)]
    assert missing == [], f"phases without a role chain: {missing}"


def test_known_phase_has_expected_owner() -> None:
    assert PHASE_ROLE_CHAIN["design"][0] is UserRole.DESIGNER
    assert PHASE_ROLE_CHAIN["development"][0] is UserRole.DEVELOPER
    assert PHASE_ROLE_CHAIN["testing"][0] is UserRole.QA


@pytest.mark.parametrize("owner", list(UATOwner))
def test_all_chained_roles_are_valid_user_roles(owner: UATOwner) -> None:
    """Guard against typos when the map is hand-edited — every value
    must be a real UserRole so capacity_provider can join against
    OrgToUser without missing rows."""
    for phase, chain in role_chains(owner).items():
        for role in chain:
            assert isinstance(role, UserRole), f"{phase} lists non-UserRole {role!r}"
