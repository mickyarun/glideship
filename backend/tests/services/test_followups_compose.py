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

"""The follow-ups DM as Slack blocks: order, due words, targets, comments and limits."""

import json
import os
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from app.repositories.followup_items import LastComment
from app.services.followups.compose import MARK_DONE_ACTION, compose_followups
from app.services.followups.done_blocks import marked_done
from app.services.followups.due_state import DueBucket, LocalDay, bucket, due_words
from app.services.followups.items import FollowupItem

ZONE = ZoneInfo("Europe/London")
# Tuesday 5 March 2030, London (GMT).
TODAY = LocalDay.of(date(2030, 3, 5), ZONE)
BASE = "https://app.example.test"
NOON = datetime(2030, 3, 5, 12, 0, tzinfo=UTC)


def _item(key: str, due_at: datetime, **kw: object) -> FollowupItem:
    fields: dict[str, object] = {
        "key": key,
        "title": f"{key} title",
        "path": f"/boards/OPS/cards/{key}",
        "stage": "Ops › Doing",
        "due_at": due_at,
        "is_target": False,
        "can_mark_done": True,
        "comment": None,
    }
    fields.update(kw)
    return FollowupItem(**fields)  # type: ignore[arg-type]


def _compose(items: list[FollowupItem], max_items: int = 15) -> list[dict[str, object]]:
    message = compose_followups(items, TODAY, max_items=max_items, comment_chars=40, base_url=BASE)
    return message.blocks


def _sections(blocks: list[dict[str, object]]) -> list[str]:
    return [b["text"]["text"] for b in blocks if b["type"] == "section"]  # type: ignore[index]


def test_buckets_and_words_count_local_dates() -> None:
    late = NOON - timedelta(days=3)
    assert bucket(late, TODAY) is DueBucket.OVERDUE and due_words(late, TODAY) == "overdue by 3d"
    assert bucket(NOON, TODAY) is DueBucket.TODAY and due_words(NOON, TODAY) == "today"
    tomorrow = NOON + timedelta(days=1)
    assert bucket(tomorrow, TODAY) is DueBucket.SOON and due_words(tomorrow, TODAY) == "tomorrow"
    assert due_words(NOON + timedelta(days=2), TODAY) == "in 2d"


def test_overdue_comes_first_then_today_then_coming_up() -> None:
    soon = _item("OPS-3", NOON + timedelta(days=1))
    today = _item("OPS-2", NOON)
    late = _item("OPS-1", NOON - timedelta(days=1))
    message = compose_followups(
        [soon, today, late], TODAY, max_items=15, comment_chars=40, base_url=BASE
    )
    keys = [text.split("|")[1].split()[0] for text in _sections(message.blocks)]
    assert keys == ["OPS-1", "OPS-2", "OPS-3"]
    assert message.text == "Follow-ups — Tue 5 Mar: 1 overdue, 1 due today, 1 coming up"
    assert message.blocks[0] == {
        "type": "header",
        "text": {"type": "plain_text", "text": "Follow-ups — Tue 5 Mar"},
    }


def test_each_item_links_back_with_its_stage_and_due_state() -> None:
    (text,) = _sections(_compose([_item("OPS-1", NOON - timedelta(days=1))]))
    assert f"<{BASE}/boards/OPS/cards/OPS-1|OPS-1 OPS-1 title>" in text
    assert "_Ops › Doing_" in text
    assert "Due Mon 4 Mar, 12:00" in text and "*overdue by 1d*" in text


def test_a_bud_target_is_worded_as_a_target_without_a_time() -> None:
    bud = _item(
        "BUD-007", NOON, is_target=True, can_mark_done=False, path="/buds/7", stage="Development"
    )
    blocks = _compose([bud])
    (text,) = _sections(blocks)
    assert "Target Tue 5 Mar" in text and "Due" not in text and "12:00" not in text
    assert all("accessory" not in b for b in blocks)


def test_a_card_carries_a_mark_done_button_keyed_by_the_card() -> None:
    (section,) = [b for b in _compose([_item("OPS-1", NOON)]) if b["type"] == "section"]
    assert section["accessory"] == {
        "type": "button",
        "text": {"type": "plain_text", "text": "Mark done"},
        "action_id": MARK_DONE_ACTION,
        "value": "OPS-1",
    }
    done = marked_done(_compose([_item("OPS-1", NOON), _item("OPS-2", NOON)]), "OPS-1")
    first, second = [b for b in done if b["type"] == "section"]
    assert "accessory" not in first and first["text"]["text"].endswith(":white_check_mark: Done")  # type: ignore[index]
    assert second["accessory"]["value"] == "OPS-2"  # type: ignore[index]


def test_the_last_comment_is_escaped_and_trimmed() -> None:
    said = LastComment(
        author="Priya <ops>",
        body="Sent the <!channel> partner a   detailed email with examples and more words",
        created_at=datetime(2030, 2, 26, 13, 52, tzinfo=UTC),
    )
    blocks = _compose([_item("OPS-1", NOON, comment=said)])
    (context,) = [b for b in blocks if b["type"] == "context" and b is not blocks[-1]]
    line = context["elements"][0]["text"]  # type: ignore[index]
    assert line.startswith("*Last comment* — Priya &lt;ops&gt;, 26 Feb, 13:52: ")
    assert "&lt;!channel&gt;" in line and "<!channel>" not in line
    assert line.endswith("…") and "   " not in line


def test_user_text_in_titles_cannot_break_out_of_the_link() -> None:
    (text,) = _sections(_compose([_item("OPS-1", NOON, title="a|b <@U1>")]))
    assert "a|b &lt;@U1&gt;" in text


def test_extra_items_are_counted_and_the_block_limit_holds() -> None:
    items = [_item(f"OPS-{n}", NOON, comment=LastComment("A", "x", NOON)) for n in range(20)]
    blocks = _compose(items)
    assert len(_sections(blocks)) == 15 and len(blocks) <= 50
    footer = blocks[-1]["elements"][0]["text"]  # type: ignore[index]
    assert footer.startswith("…and 5 more") and "/profile/notifications" in footer


def test_rendered_payload_is_valid_block_kit_json() -> None:
    """Writes the payload for a manual look in Slack's Block Kit Builder when asked."""
    items = [
        _item("OPS-12", NOON - timedelta(days=1), comment=LastComment("Sam", "Sent it", NOON)),
        _item("BUD-042", NOON, is_target=True, can_mark_done=False, path="/buds/42"),
        _item("SEO-3", NOON + timedelta(days=2), stage="SEO › Review"),
    ]
    blocks = _compose(items)
    payload = json.dumps({"blocks": blocks})
    for block in blocks:
        assert block["type"] in {"header", "divider", "section", "context"}
    header = blocks[0]["text"]["text"]  # type: ignore[index]
    assert len(header) <= 150
    if out := os.environ.get("FOLLOWUPS_PAYLOAD_OUT"):
        Path(out).write_text(payload)
