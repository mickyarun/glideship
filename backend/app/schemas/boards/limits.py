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

"""The limits the boards UI enforces, served so the frontend never copies them."""

from pydantic import BaseModel

from app.schemas.boards.card_detail import AttachmentLimits


class BoardLimits(BaseModel):
    """Lengths, caps and page sizes for boards, cards and their threads."""

    board_name_max: int
    board_key_min: int
    board_key_max: int
    board_description_max: int
    stage_name_max: int
    max_stages: int
    wip_limit_max: int
    label_name_max: int
    card_title_max: int
    card_description_max: int
    doc_max: int
    comment_max: int
    checklist_text_max: int
    checklist_max_items: int
    links_max_per_card: int
    id_list_max_items: int
    search_max: int
    filters_max_bytes: int
    stage_page_size: int
    recent_done_days: int
    # The largest import export file the upload route accepts, in whole MB.
    import_max_upload_mb: int
    attachments: AttachmentLimits
