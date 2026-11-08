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

"""Role template matching, possible duplicate accounts and per-viewer facts (pure)."""

import uuid

from app.core.permission_deps import PermissionSet
from app.models.appraisal_role_template import AppraisalRoleTemplate
from app.repositories.appraisal_identity import LooseAccount
from app.services.appraisals.fact_view import for_viewer
from app.services.appraisals.identity import Person, possible_duplicates
from app.services.appraisals.role_templates import match_template, seed_templates


def _templates() -> list[AppraisalRoleTemplate]:
    out = []
    for seed in seed_templates():
        template = AppraisalRoleTemplate(**seed.model_dump(mode="json"))
        template.id = uuid.uuid4()
        out.append(template)
    return out


def _name(template: AppraisalRoleTemplate | None) -> str | None:
    return template.name if template else None


def test_department_wins_then_the_first_designation_word() -> None:
    templates = _templates()
    assert _name(match_template(templates, "Customer Support", "Senior Engineer")) == "Support"
    assert _name(match_template(templates, None, "QA Engineer")) == "QA"
    assert _name(match_template(templates, None, "Support Engineer")) == "Support"
    assert _name(match_template(templates, None, "Senior Software Engineer")) == "Engineering"


def test_whole_words_only() -> None:
    # "ui" is inside "build"; that must not make this a Design role.
    assert _name(match_template(_templates(), None, "Build Engineer")) == "Engineering"


def test_fallback_and_overrides() -> None:
    templates = _templates()
    assert _name(match_template(templates, "Facilities", "Office manager")) == "General"
    support = next(t for t in templates if t.name == "Support")
    chosen = match_template(templates, "Facilities", None, {"Facilities": str(support.id)})
    assert _name(chosen) == "Support"
    assert match_template([t for t in templates if not t.is_default], "Facilities", None) is None


def _loose(name: str, email: str, login: str | None = None) -> LooseAccount:
    return LooseAccount(uuid.uuid4(), name, email, login)


def test_possible_duplicates_by_name_or_login() -> None:
    me = Person(uuid.uuid4(), "Meera Iyer", "meera.iyer@northwind.example", "meera-i")
    same_name = _loose("meera  IYER", "x@y.example")
    noreply = _loose("m", "123+meera-i@users.noreply.github.com")
    someone = _loose("Meera Rao", "meera.rao@northwind.example")
    found = possible_duplicates(me, [same_name, noreply, someone])
    assert found == [same_name, noreply]


FACTS = [
    {
        "source": "board_cards",
        "id": "c1",
        "key": "OPS-1",
        "title": "Close",
        "url": "/b",
        "board_id": str(uuid.uuid4()),
    },
    {"source": "pull_requests", "id": "p1", "key": "PR #1", "title": "Fix", "url": "https://gh"},
    {
        "source": "hr_records",
        "id": "h1",
        "key": "Leave setup",
        "title": "Set up policy",
        "url": "/leave",
    },
]
NOBODY = PermissionSet(ids=frozenset(), is_owner=False)


def test_the_person_sees_everything_they_did() -> None:
    assert not any(
        f["private"] for f in for_viewer(FACTS, is_self=True, perms=NOBODY, boards=set())
    )


def test_others_see_only_what_they_could_open() -> None:
    board = uuid.UUID(FACTS[0]["board_id"])
    perms = PermissionSet(ids=frozenset({"workspace:engineering"}), is_owner=False)
    shown = for_viewer(FACTS, is_self=False, perms=perms, boards={board})
    assert [f["private"] for f in shown] == [False, False, True]
    hidden = shown[2]
    assert (
        hidden["title"] is None
        and hidden["url"] is None
        and hidden["key"] == "private record · HR"
    )


def test_nothing_shows_to_someone_with_no_access() -> None:
    shown = for_viewer(FACTS, is_self=False, perms=NOBODY, boards=set())
    assert all(f["private"] and f["title"] is None for f in shown)
