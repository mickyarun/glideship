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


"""Copying a card's uploaded source files into our storage (API mode only).

Each file passes the card attachment rules (type, per-file size, files
per card) and the import's byte budget. The source supplies only the
download; a file that can't be copied stays on the card as a link.
"""

from collections.abc import Awaitable, Callable, Iterable

from app.services.attachment_upload import UploadRejectedError, precheck, store
from app.services.boards.attachment_rules import policy
from app.services.file_storage import get_file_storage
from app.services.imports.context import ImportContext
from app.services.imports.draft import AttachmentDraft
from app.services.imports.prefetch import FetchedItem

# Bytes of one attachment, at most ``limit`` of them; None keeps it a link.
Download = Callable[[AttachmentDraft, int], Awaitable[bytes | None]]
KEPT_AS_LINK = "files_kept_as_links"


async def copy_files(
    ctx: ImportContext, attachments: Iterable[AttachmentDraft], download: Download
) -> FetchedItem:
    """Every uploaded attachment that fits, stored, by attachment id."""
    rules = policy()
    fetched = FetchedItem()
    for attachment in attachments:
        if not attachment.is_upload:
            continue
        try:
            name = precheck(rules, attachment.name, len(fetched.files))
        except UploadRejectedError:
            fetched.dropped[KEPT_AS_LINK] += 1
            continue
        limit = min(rules.max_bytes, ctx.budget.remaining)
        data = await download(attachment, limit) if limit else None
        if data is None:
            fetched.dropped[KEPT_AS_LINK] += 1
            continue
        try:
            copy = await store(
                rules,
                get_file_storage(),
                org_id=ctx.org_id,
                folder=f"board-attachments/{ctx.board.key}/import-{ctx.session.id}",
                name=name,
                data=data,
            )
        except UploadRejectedError:
            fetched.dropped[KEPT_AS_LINK] += 1
            continue
        ctx.budget.spend(copy.size_bytes)
        fetched.files[attachment.id] = copy
    return fetched
