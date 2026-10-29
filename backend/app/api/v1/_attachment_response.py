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

"""Serve a stored attachment back as a download, the same way for every surface.

Always ``attachment`` disposition: nothing in the UI renders user content
inline (tiles fetch the bytes and use a blob URL), so a same-origin
browsing context is never offered. ``nosniff`` stops a browser running,
say, a ``.png`` full of HTML, and the sandbox CSP strips scripting and
same-origin access, which matters for PDFs. The filename is re-sanitised,
so the header stays latin-1 clean with no quotes, CR or LF in it.
"""

from fastapi.responses import Response

from app.core.paths import sanitize_filename


def attachment_response(data: bytes, filename: str, mime_type: str) -> Response:
    """The file's bytes with the download headers every attachment route sends."""
    safe_name = sanitize_filename(filename, fallback="attachment")
    return Response(
        content=data,
        media_type=mime_type,
        headers={
            "Content-Disposition": f'attachment; filename="{safe_name}"',
            "X-Content-Type-Options": "nosniff",
            "Content-Security-Policy": "default-src 'none'; sandbox",
        },
    )
