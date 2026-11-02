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

"""The "From the board" section is safe markdown; only the card's own text is requirements."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from tests.integration.board_api_support import ok
from tests.integration.board_handover_support import card, desk, hand_over, preview, stubbed
from tests.integration.board_notify_support import fake_slack
from tests.integration.bud_lifecycle_support import (
    app_database_blocked as app_database_blocked,
)
from tests.integration.scan_features_bugs_support import Factory

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def _slack(monkeypatch: pytest.MonkeyPatch, pg_session_factory: Factory) -> None:
    fake_slack(monkeypatch, pg_session_factory)


async def test_card_text_cannot_add_headings_or_break_links(
    client: AsyncClient, pg_session_factory: Factory
) -> None:
    """A checklist item with a newline and ``#``, a link whose URL has ``)``."""
    d = await desk(client, pg_session_factory)
    url = await card(client, d, description_md="Plans")
    h = d.pm.headers
    for text in ("Copy\n# Not a heading", "# Nor this"):
        ok(await client.post(f"{url}/checklist", json={"text": text}, headers=h), 201)
    link = {"url": "https://example.com/wiki/Plan_(pricing)", "title": "Spec [v2]"}
    ok(await client.post(f"{url}/attachments/links", json=link, headers=h), 201)
    with stubbed():
        body = ok(await preview(client, d.pm, url))["requirements_md"]

    # Joined onto one line, and a leading ``#`` escaped: neither starts a heading.
    assert "- [ ] Copy # Not a heading" in body and "- [ ] \\# Nor this" in body
    assert "\n#" not in body.replace("\n## From the board", "")
    assert "- [Spec \\[v2\\]](<https://example.com/wiki/Plan_(pricing)>)" in body


async def test_an_edited_text_with_only_the_board_section_cannot_go_to_the_tech_plan(
    client: AsyncClient, pg_session_factory: Factory
) -> None:
    """422 HANDOVER_NEEDS_REQUIREMENTS: the generated section isn't something to plan from."""
    d = await desk(client, pg_session_factory)
    url = await card(client, d, description_md="Plans")
    with stubbed():
        drafted = ok(await preview(client, d.pm, url))["requirements_md"]
        section = drafted[drafted.index("## From the board") :]
        refused = await hand_over(
            client,
            d.pm,
            url,
            target_status="tech_arch",
            overrides={"requirements_md": f"\n\n{section}"},
        )
        kept = await hand_over(
            client,
            d.pm,
            url,
            target_status="tech_arch",
            overrides={"requirements_md": f"Edited plans\n\n{section}"},
        )
    assert (refused.status_code, refused.json()["code"]) == (422, "HANDOVER_NEEDS_REQUIREMENTS")
    assert kept.status_code == 201, kept.text
