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


"""The board import tunables stay inside what the platform can serve."""

import pytest
from pydantic import ValidationError

from app.config_board_imports import (
    IMPORT_MAPPING_MAX_ENTRIES,
    IMPORT_UPLOAD_CEILING_BYTES,
    BoardImportSettings,
)
from app.core.body_limit import MAX_REQUEST_BODY_BYTES


def test_the_upload_cap_defaults_to_the_body_limit_less_its_framing_room() -> None:
    cfg = BoardImportSettings()
    assert cfg.import_max_upload_bytes == IMPORT_UPLOAD_CEILING_BYTES
    # The body limit leaves 1 MB for multipart framing, so an upload at the
    # cap still reaches the route and gets its own clear 413.
    assert MAX_REQUEST_BODY_BYTES - IMPORT_UPLOAD_CEILING_BYTES == 1024 * 1024
    assert cfg.trello_requests_per_10s == 80


def test_an_upload_cap_above_the_body_limit_is_refused() -> None:
    with pytest.raises(ValidationError, match="request body limit"):
        BoardImportSettings(import_max_upload_bytes=IMPORT_UPLOAD_CEILING_BYTES + 1)


def test_list_and_member_caps_stay_mappable() -> None:
    with pytest.raises(ValidationError):
        BoardImportSettings(import_max_lists=IMPORT_MAPPING_MAX_ENTRIES + 1)
