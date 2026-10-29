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

"""Bug comments and attachments keep their behaviour on the shared thread repository."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest

from app.models.bug import Bug
from app.models.bug_attachment import BugAttachment
from app.models.bug_comment import BugComment
from app.repositories.bug_attachment import BugAttachmentRepository
from app.repositories.bug_comment import BugCommentRepository
from app.repositories.thread import is_comment_author
from tests.integration.scan_features_bugs_support import Factory, new_member, new_org

pytestmark = pytest.mark.integration

T0 = datetime(2026, 1, 5, 9, 0, tzinfo=UTC)


async def _bug(factory: Factory) -> tuple[uuid.UUID, uuid.UUID, uuid.UUID]:
    """(org, reporter, bug) for a fresh org."""
    org = await new_org(factory)
    reporter = await new_member(factory, org)
    async with factory() as db:
        bug = Bug(org_id=org, bug_number=1, title="Broken", reporter_id=reporter)
        db.add(bug)
        await db.commit()
        return org, reporter, bug.id


async def test_comment_thread_order_tombstones_and_counts(pg_session_factory: Factory) -> None:
    org, author, bug = await _bug(pg_session_factory)
    async with pg_session_factory() as db:
        # Added out of order: the thread sorts by created_at, not insert order.
        for minutes, body in [(2, "third"), (0, "first"), (1, "second")]:
            db.add(
                BugComment(
                    org_id=org,
                    bug_id=bug,
                    author_id=author,
                    body=body,
                    created_at=T0 + timedelta(minutes=minutes),
                )
            )
        await db.commit()
    async with pg_session_factory() as db:
        repo = BugCommentRepository(db, org_id=org)
        thread = await repo.list_for_bug(bug)
        assert [c.body for c in thread] == ["first", "second", "third"]
        edited = await repo.update_body(thread[0], "first, edited")
        assert edited.edited_at is not None
        await repo.soft_delete(thread[1])
        await db.commit()
    async with pg_session_factory() as db:
        repo = BugCommentRepository(db, org_id=org)
        assert len(await repo.list_for_bug(bug)) == 3
        live = await repo.list_for_bug(bug, include_deleted=False)
        assert [c.body for c in live] == ["first, edited", "third"]
        assert await repo.count_active_by_bug([bug, uuid.uuid4()]) == {bug: 2}
        assert await repo.count_active_by_bug([]) == {}
        stranger = BugCommentRepository(db, org_id=await new_org(pg_session_factory))
        assert await stranger.list_for_bug(bug) == []
        assert await stranger.get_by_id(thread[0].id) is None


async def test_attachments_list_oldest_first_and_count_per_org(
    pg_session_factory: Factory,
) -> None:
    org, uploader, bug = await _bug(pg_session_factory)
    async with pg_session_factory() as db:
        for minutes, name in [(1, "b.png"), (0, "a.png")]:
            db.add(
                BugAttachment(
                    org_id=org,
                    bug_id=bug,
                    filename=name,
                    mime_type="image/png",
                    size_bytes=10,
                    storage_path=f"bugs/{bug}/{name}",
                    uploaded_by=uploader,
                    created_at=T0 + timedelta(minutes=minutes),
                )
            )
        await db.commit()
    async with pg_session_factory() as db:
        repo = BugAttachmentRepository(db, org_id=org)
        assert [a.filename for a in await repo.list_for_bug(bug)] == ["a.png", "b.png"]
        assert await repo.count_for_bug(bug) == 2
        stranger = BugAttachmentRepository(db, org_id=await new_org(pg_session_factory))
        assert await stranger.count_for_bug(bug) == 0
        assert await stranger.list_for_bug(bug) == []


async def test_rows_are_fetched_only_through_their_own_parent(
    pg_session_factory: Factory,
) -> None:
    org, author, bug = await _bug(pg_session_factory)
    async with pg_session_factory() as db:
        other = Bug(org_id=org, bug_number=2, title="Other", reporter_id=author)
        db.add(other)
        await db.flush()
        comment = BugComment(org_id=org, bug_id=bug, author_id=author, body="mine")
        db.add(comment)
        await db.commit()
    async with pg_session_factory() as db:
        repo = BugCommentRepository(db, org_id=org)
        found = await repo.get_in_parent(bug, comment.id)
        assert found is not None and found.body == "mine"
        assert await repo.get_in_parent(other.id, comment.id) is None
        assert await repo.count_for_parent(bug) == 1
        assert await repo.count_for_parent(bug, BugComment.deleted_at.is_not(None)) == 0
        assert is_comment_author(found, author)
        assert not is_comment_author(found, uuid.uuid4())
