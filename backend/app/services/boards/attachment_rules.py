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

"""What a card accepts as an attachment, from ``BoardsConfig``."""

from app.config import settings
from app.schemas.boards.card_detail import AttachmentLimits
from app.services.upload_policy import UploadPolicy, card_attachment_policy


def policy() -> UploadPolicy:
    """What a card accepts, from ``BoardsConfig``."""
    return card_attachment_policy(
        max_file_mb=settings.boards.attachment_max_file_mb,
        max_files=settings.boards.attachment_max_files,
    )


def limits() -> AttachmentLimits:
    """The card policy as the picker reads it."""
    rules = policy()
    return AttachmentLimits(
        max_file_mb=rules.max_mb,
        max_files=rules.max_files or 0,
        accepted_extensions=sorted(rules.extensions or {}),
    )
