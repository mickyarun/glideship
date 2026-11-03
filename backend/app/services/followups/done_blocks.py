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

"""A follow-ups message after one of its cards was marked done (pure, no I/O)."""

from typing import Any

from app.services.followups.compose import MARK_DONE_ACTION

DONE_SUFFIX = "  ·  :white_check_mark: Done"


def _is_button_for(block: dict[str, Any], key: str) -> bool:
    accessory = block.get("accessory") or {}
    return accessory.get("action_id") == MARK_DONE_ACTION and accessory.get("value") == key


def marked_done(blocks: list[dict[str, Any]], key: str) -> list[dict[str, Any]]:
    """``blocks`` with the card ``key``'s button swapped for a "Done" mark."""
    updated = []
    for block in blocks:
        if block.get("type") == "section" and _is_button_for(block, key):
            text = block["text"]
            block = {k: v for k, v in block.items() if k not in ("accessory", "text", "block_id")}
            block["text"] = {**text, "text": text["text"] + DONE_SUFFIX}
        updated.append(block)
    return updated
