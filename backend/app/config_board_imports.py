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


"""Tunables for imports into boards, part of ``BoardsConfig`` (``BOARDS_*`` variables).

Uploads ride the global request body limit, so the upload cap can never be
set above it; boards bigger than that come in over the source's API, whose
snapshot has its own cap. The count caps are checked on the raw JSON before
any model is built, so an oversized export is refused cheaply.
"""

from typing import Final

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings

from app.core.upload_limits import MAX_CONFIGURABLE_ATTACHMENT_MB, MIB

# The upload cap's ceiling: the largest file the body limit lets through
# with room for the multipart framing.
IMPORT_UPLOAD_CEILING_BYTES: Final = MAX_CONFIGURABLE_ATTACHMENT_MB * MIB
# Lists and members one reviewed mapping may name; the count caps stay under it.
IMPORT_MAPPING_MAX_ENTRIES: Final = 2000
GIB: Final = 1024 * MIB


class BoardImportSettings(BaseSettings):
    """Import tunables: sizes, counts, abuse limits, retention and the Trello client."""

    import_max_upload_bytes: int = Field(
        default=IMPORT_UPLOAD_CEILING_BYTES, gt=0, description="Largest uploaded export."
    )
    import_max_snapshot_bytes: int = Field(
        default=200 * MIB, gt=0, description="Largest board an API-mode fetch may read."
    )
    import_max_cards: int = Field(default=20_000, gt=0, description="Cards one import may hold.")
    import_max_actions: int = Field(
        default=200_000, gt=0, description="Actions (comments) one import may hold."
    )
    import_max_lists: int = Field(default=500, gt=0, description="Lists one import may hold.")
    import_max_members: int = Field(default=1000, gt=0, description="Members one import names.")
    import_max_labels: int = Field(default=1000, gt=0, description="Labels one import may hold.")
    import_max_checklists: int = Field(
        default=50_000, gt=0, description="Checklists one import may hold."
    )
    import_max_check_items: int = Field(
        default=250_000, gt=0, description="Checklist lines one import may hold."
    )
    import_max_attachment_bytes: int = Field(
        default=GIB, gt=0, description="Attachment bytes one import may copy, across resumes."
    )
    import_org_attachment_bytes_per_day: int = Field(
        default=5 * GIB, gt=0, description="Attachment bytes an org's imports copy per day."
    )
    import_batch_size: int = Field(
        default=50, gt=0, description="Cards one import commits at a time."
    )
    import_max_open_per_user: int = Field(
        default=5, gt=0, description="Unfinished imports one person may have."
    )
    import_max_open_per_org: int = Field(
        default=25, gt=0, description="Unfinished imports one org may have."
    )
    import_creates_per_window: int = Field(
        default=20, gt=0, description="Imports one person may start per window."
    )
    import_create_window_seconds: int = Field(
        default=3600, gt=0, description="The window the start limit counts over."
    )
    import_busy_retry_after_seconds: int = Field(
        default=30, gt=0, description="Retry-After sent when the job queue is full."
    )
    import_session_retention_days: int = Field(
        default=14, gt=0, description="Days an unfinished import is kept untouched."
    )
    import_sweep_interval_seconds: int = Field(
        default=3600, gt=0, description="How often abandoned imports are cleaned up."
    )
    trello_requests_per_10s: int = Field(
        default=80, gt=0, description="Trello API calls per 10 seconds per token."
    )
    trello_timeout_seconds: float = Field(
        default=30.0, gt=0, description="How long one Trello API call may take."
    )
    trello_max_retries: int = Field(
        default=5, ge=0, description="Retries of a Trello call that was limited or failed."
    )
    trello_backoff_seconds: float = Field(
        default=2.0, gt=0, description="First wait before a retry; doubles on each one."
    )
    trello_max_wait_seconds: float = Field(
        default=60.0, gt=0, description="Longest wait a Trello Retry-After may ask for."
    )
    trello_limiter_tokens: int = Field(
        default=256, gt=0, description="Trello tokens whose call windows are remembered."
    )

    @model_validator(mode="after")
    def _within_platform_limits(self) -> "BoardImportSettings":
        """An upload cap above the body limit could never be reached; mappings stay valid."""
        if self.import_max_upload_bytes > IMPORT_UPLOAD_CEILING_BYTES:
            raise ValueError(
                "BOARDS_IMPORT_MAX_UPLOAD_BYTES can't exceed the request body limit "
                f"({IMPORT_UPLOAD_CEILING_BYTES} bytes); use API mode for bigger boards"
            )
        if max(self.import_max_lists, self.import_max_members) > IMPORT_MAPPING_MAX_ENTRIES:
            raise ValueError(
                f"BOARDS_IMPORT_MAX_LISTS and _MEMBERS can't exceed {IMPORT_MAPPING_MAX_ENTRIES}"
            )
        return self
