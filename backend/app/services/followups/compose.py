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

"""One person's follow-ups DM as Slack blocks (pure, no I/O).

Overdue items come first, oldest first, then today's, then the ones
coming up; up to ``max_items`` in all, the rest counted as "and N more".
Every item is a section (linked key and title, stage, due state) and,
when it has one, a context line with its last comment.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from app.services.followups.due_state import DueBucket, LocalDay, bucket, due_words
from app.services.followups.items import FollowupItem
from app.services.slack_mrkdwn import escape_mrkdwn

SETTINGS_PATH = "/profile/notifications"
# Keeps a section well inside Slack's 3000 characters even after escaping.
TITLE_CHARS = 200
_ORDER = (DueBucket.OVERDUE, DueBucket.TODAY, DueBucket.SOON)
_SUMMARY = {
    DueBucket.OVERDUE: "overdue",
    DueBucket.TODAY: "due today",
    DueBucket.SOON: "coming up",
}


@dataclass(frozen=True)
class FollowupMessage:
    """The blocks, and the plain text Slack shows in notifications."""

    text: str
    blocks: list[dict[str, Any]]


def _mrkdwn(text: str) -> dict[str, str]:
    return {"type": "mrkdwn", "text": text}


def _excerpt(body: str, limit: int) -> str:
    flat = " ".join(body.split())
    return flat if len(flat) <= limit else flat[: limit - 1].rstrip() + "…"


def _item_blocks(
    item: FollowupItem, local: LocalDay, base_url: str, comment_chars: int
) -> list[dict[str, Any]]:
    when = item.due_at.astimezone(local.zone)
    words = due_words(item.due_at, local)
    late = bucket(item.due_at, local) is DueBucket.OVERDUE
    label = f"Target {when:%a %-d %b}" if item.is_target else f"Due {when:%a %-d %b, %H:%M}"
    state = f":rotating_light: *{words}*" if late else f":hourglass_flowing_sand: {words}"
    title = escape_mrkdwn(_excerpt(item.title, TITLE_CHARS))
    link = f"<{base_url}{item.path}|{item.key} {title}>"
    text = f"*{link}*  ·  _{escape_mrkdwn(item.stage)}_\n{label}  ·  {state}"
    blocks: list[dict[str, Any]] = [{"type": "section", "text": _mrkdwn(text)}]
    if item.comment is not None:
        said = item.comment.created_at.astimezone(local.zone)
        line = (
            f"*Last comment* — {escape_mrkdwn(item.comment.author)}, {said:%-d %b, %H:%M}: "
            f"{escape_mrkdwn(_excerpt(item.comment.body, comment_chars))}"
        )
        blocks.append({"type": "context", "elements": [_mrkdwn(line)]})
    return blocks


def compose_followups(
    items: Sequence[FollowupItem],
    local: LocalDay,
    *,
    max_items: int,
    comment_chars: int,
    base_url: str,
) -> FollowupMessage:
    """One person's DM for their ``items`` (at least one)."""
    ranked = sorted(items, key=lambda i: (_ORDER.index(bucket(i.due_at, local)), i.due_at, i.key))
    title = f"Follow-ups — {local.day:%a %-d %b}"
    counts = {b: sum(1 for i in ranked if bucket(i.due_at, local) is b) for b in _ORDER}
    summary = ", ".join(f"{n} {_SUMMARY[b]}" for b, n in counts.items() if n)
    blocks: list[dict[str, Any]] = [
        {"type": "header", "text": {"type": "plain_text", "text": title}}
    ]
    for item in ranked[:max_items]:
        blocks.append({"type": "divider"})
        blocks.extend(_item_blocks(item, local, base_url, comment_chars))
    footer = []
    if len(ranked) > max_items:
        footer.append(f"…and {len(ranked) - max_items} more")
    footer.append(f"<{base_url}{SETTINGS_PATH}|Change when this arrives>")
    blocks.append({"type": "context", "elements": [_mrkdwn("  ·  ".join(footer))]})
    return FollowupMessage(text=f"{title}: {summary}", blocks=blocks)
