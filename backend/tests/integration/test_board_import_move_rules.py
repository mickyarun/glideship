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

"""An import places cards without the stages' entry rules."""

from __future__ import annotations

from pathlib import Path

import pytest
from httpx import AsyncClient

from tests.integration.board_api_support import BOARDS, make_board, ok, put_role, stage_id
from tests.integration.board_import_support import (
    IMPORTS,
    Jobs,
    board_cards,
    capture_jobs,
    mapping,
    named,
    parsed,
    save_and_start,
    use_import_storage,
)
from tests.integration.board_move_support import FIELDS
from tests.integration.scan_features_bugs_support import Factory, new_org
from tests.services.trello_fixture import BACKLOG, DOING, DONE, OLD

pytestmark = pytest.mark.integration


@pytest.fixture
def jobs(pg_session_factory: Factory, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Jobs:
    use_import_storage(tmp_path, monkeypatch)
    return capture_jobs(pg_session_factory, monkeypatch)


async def test_imported_cards_land_in_stages_whatever_they_require(
    client: AsyncClient, pg_session_factory: Factory, jobs: Jobs
) -> None:
    org = await new_org(pg_session_factory)
    pm = await named(pg_session_factory, org, "Pat Manager", "pm")
    priya = await named(pg_session_factory, org, "Priya Sharma")
    board = await make_board(client, pm, template="ops")
    key = board["board"]["key"]
    await put_role(client, pm, key, priya.id, "editor")
    for stage in board["stages"]:
        url = f"{BOARDS}/{key}/stages/{stage['id']}"
        ok(await client.patch(url, json={"required_fields": list(FIELDS)}, headers=pm.headers))
    groups = [
        {"group_id": BACKLOG, "action": "existing", "stage_id": stage_id(board, "Backlog")},
        {"group_id": DOING, "action": "existing", "stage_id": stage_id(board, "In progress")},
        {"group_id": DONE, "action": "existing", "stage_id": stage_id(board, "Done")},
        {"group_id": OLD, "action": "skip"},
    ]
    body = mapping({"kind": "existing", "key": key}, groups=groups, priya=priya.id)
    session = await parsed(client, pm, jobs)
    await save_and_start(client, pm, session, body)
    await jobs.run_all()
    result = ok(await client.get(f"{IMPORTS}/{session}", headers=pm.headers))
    assert result["status"] == "completed"
    assert result["result"]["imported"] > 0 and result["result"]["failed"] == 0
    cards = await board_cards(pg_session_factory, board["board"]["id"])
    assert len(cards) == result["result"]["imported"]
    assert str(cards[0].stage_id) in {g.get("stage_id") for g in groups}
