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

"""Several channels for the who's-out post, and settings saved with one."""

from unittest.mock import AsyncMock

import pytest

from app.schemas.leave_digest import LeaveDigestSettings
from app.services.leave import digest_post


def test_old_single_channel_settings_still_load() -> None:
    settings = LeaveDigestSettings.model_validate({"enabled": True, "channel_id": "C0123456"})
    assert settings.channel_ids == ["C0123456"]


def test_duplicate_channels_collapse_and_bad_ids_are_refused() -> None:
    settings = LeaveDigestSettings(channel_ids=["C0123456", "C0123456", "G9999999"])
    assert settings.channel_ids == ["C0123456", "G9999999"]
    with pytest.raises(ValueError):
        LeaveDigestSettings(channel_ids=["general"])


async def test_every_channel_is_tried_even_when_one_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    post = AsyncMock(side_effect=[("C1", "1", "not_in_channel"), ("C2", "2", "")])
    monkeypatch.setattr(digest_post, "post_message", post)
    errors = await digest_post.post_to_channels("tok", ["C0000001", "C0000002"], "hi")
    assert errors == ["not_in_channel"]
    assert post.await_count == 2
