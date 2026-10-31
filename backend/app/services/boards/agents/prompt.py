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

"""A card run's prompt: the skill's own prompt, then the card it works on.

The card's context goes in as JSON, followed by the board's linked
repositories by name. The agent is told to save its result with
``write_card_doc`` (a draft for review); a provider without tools replies
with the document, which the run then saves the same way.
"""

import json
from typing import Any

from app.models.board_enums import BoardCardDocKind
from app.services.boards.constants import WRITE_CARD_DOC_TOOL

NO_REPOS = "None are linked to this board."


def _repo_lines(context: dict[str, Any]) -> str:
    repos = context.get("linked_repos") or []
    if not repos:
        return NO_REPOS
    return "\n".join(
        f"- {r['name']}" + (f" ({r['full_name']})" if r["full_name"] else "") for r in repos
    )


def build_card_prompt(skill_prompt: str, context: dict[str, Any], kind: BoardCardDocKind) -> str:
    """The full prompt for one run on one card."""
    card = context["card"]
    board = context["board"]
    return f"""{skill_prompt.strip()}

---

## The card you are working on

You are working on board card {card["key"]} ("{card["title"]}") on the {board["name"]} board.

Save your result with the `{WRITE_CARD_DOC_TOOL}` tool: `card_id` "{card["id"]}", `kind`
"{kind.value}", and `content_md` set to the whole document in Markdown. It is saved as a
draft for a person to review; it doesn't change the card. Use only names, people and dates
that appear in the context below. If you can't call tools, reply with the document itself
and nothing else.

## Card context (JSON)

```json
{json.dumps(context, indent=2, ensure_ascii=False)}
```

## Linked repositories

{_repo_lines(context)}
"""
