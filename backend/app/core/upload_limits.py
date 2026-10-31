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


"""The largest request bodies the backend and its proxy accept, with no imports.

Settings, the body-limit middleware and the board import config all read
these, so the constants live where importing them costs nothing.
"""

from typing import Final

MIB: Final = 1024 * 1024

# Hard ceiling on the per-org bug-attachment size limit, in MB.
#
# This is NOT a preference — it is the largest body the edge proxy will
# forward. ``frontend/nginx.conf.template`` sets ``client_max_body_size``
# just above this value so a request at the configured limit still
# reaches the backend and gets a clean JSON 413 instead of nginx's HTML
# error page. Raising this constant means raising that directive too,
# or admins can save a limit that silently fails at the proxy.
MAX_CONFIGURABLE_ATTACHMENT_MB: Final = 25

# 1 MB above the largest attachment an org can allow, like the proxy:
# multipart framing fits, and an at-the-limit upload still gets the
# route's own clear message. Keep in step with nginx's client_max_body_size.
MAX_REQUEST_BODY_MB: Final = MAX_CONFIGURABLE_ATTACHMENT_MB + 1
MAX_REQUEST_BODY_BYTES: Final = MAX_REQUEST_BODY_MB * MIB
