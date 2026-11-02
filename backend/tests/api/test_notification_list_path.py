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


"""The notification list answers at the path the web app calls, in one request.

The app runs with ``redirect_slashes=False``, so ``/api/v1/notifications/``
(what the notification store fetches) is answered directly and the
slash-less spelling is a plain 404, never a 307 back to the slashed one. A
second ``GET /notifications/`` on page load is therefore a second fetch by
the client, not a redirect hop.
"""

from httpx import ASGITransport, AsyncClient

from app.main import app

LIST = "/api/v1/notifications/"


async def test_the_list_path_is_served_without_a_redirect() -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        listed = await client.get(LIST, follow_redirects=False)
        bare = await client.get(LIST.rstrip("/"), follow_redirects=False)
    # No token: the route is found and refuses the caller; nothing redirects.
    assert listed.status_code == 401
    assert bare.status_code == 404
