"""appraisal send, due dates and open answers

Check-ins and manager notes become private to their writer until sent,
and both get due dates: a check-in five working days after its period
ends, a manager note five working days after the check-in it answers is
sent (a cycle's ``feedback_due_days`` now counts from that send). The
self-review gains two open answers.

Existing data carries forward. Everything people could read before this
migration stays readable: every existing check-in, and every manager
note with something written in it, is marked sent at its last update.
Existing check-ins get a due date five weekdays after their period (the
person's holidays aren't known here). Existing notes keep the due date
they had. Running cycles and stored org settings take the decided five
days for notes; orgs get ``min_goals`` of three, or their ``max_goals``
when that is lower. Autogenerate doesn't compare check constraints, so
that swap is spelled out.

Revision ID: 6d2d593be9c9
Revises: 52934796567f
Create Date: 2026-11-24 13:54:49.624024

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "6d2d593be9c9"
down_revision: str | None = "52934796567f"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

DUE_DAYS = 5
OLD_FEEDBACK_DUE_DAYS = 10

# The fifth weekday after each existing check-in's period ends.
CHECK_IN_DUE = f"""
UPDATE appraisal_check_ins c SET due_on = (
    SELECT d::date FROM generate_series(c.period_end + 1, c.period_end + 14, interval '1 day') d
    WHERE extract(isodow FROM d) < 6 ORDER BY d OFFSET {DUE_DAYS - 1} LIMIT 1
)
WHERE due_on IS NULL
"""

SETTINGS = f"""
UPDATE organizations SET config = jsonb_set(
    config,
    '{{appraisals}}',
    (config -> 'appraisals') || jsonb_build_object(
        'min_goals', LEAST(3, COALESCE((config -> 'appraisals' ->> 'max_goals')::int, 3)),
        'checkin_due_days', {DUE_DAYS},
        'feedback_due_days', {DUE_DAYS}
    )
)
WHERE jsonb_typeof(config -> 'appraisals') = 'object'
"""

# Run after the schema changes; a test runs the same statements.
BACKFILL = (
    "UPDATE appraisal_check_ins SET sent_at = updated_at WHERE sent_at IS NULL",
    CHECK_IN_DUE,
    "UPDATE appraisal_manager_feedback SET sent_at = updated_at"
    " WHERE sent_at IS NULL AND (keep_note IS NOT NULL OR try_note IS NOT NULL"
    " OR goal_status <> '{}'::jsonb)",
    f"UPDATE appraisal_cycles SET feedback_due_days = {DUE_DAYS}",
    SETTINGS,
)


def upgrade() -> None:
    op.add_column("appraisal_check_ins", sa.Column("due_on", sa.Date(), nullable=True))
    op.add_column(
        "appraisal_check_ins", sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column(
        "appraisal_check_ins",
        sa.Column("edited_after_send_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_appraisal_check_ins_unsent",
        "appraisal_check_ins",
        ["org_id", "due_on"],
        unique=False,
        postgresql_where="sent_at IS NULL",
    )
    op.add_column(
        "appraisal_cycles",
        sa.Column("checkin_due_days", sa.SmallInteger(), server_default="5", nullable=False),
    )
    op.drop_constraint("ck_appraisal_cycles_offsets", "appraisal_cycles", type_="check")
    op.create_check_constraint(
        "ck_appraisal_cycles_offsets",
        "appraisal_cycles",
        "feedback_due_days >= 0 AND checkin_due_days >= 1 AND hr_overdue_offset >= 0",
    )
    op.add_column(
        "appraisal_manager_feedback",
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "appraisal_manager_feedback",
        sa.Column("edited_after_send_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.alter_column("appraisal_manager_feedback", "due_on", existing_type=sa.DATE(), nullable=True)
    op.create_index(
        "ix_appraisal_feedback_unsent",
        "appraisal_manager_feedback",
        ["org_id", "manager_user_id"],
        unique=False,
        postgresql_where="sent_at IS NULL",
    )
    op.add_column("appraisals", sa.Column("self_proud", sa.LargeBinary(), nullable=True))
    op.add_column("appraisals", sa.Column("self_differently", sa.LargeBinary(), nullable=True))

    # Existing data: nothing readable yesterday disappears today.
    for statement in BACKFILL:
        op.execute(statement)


def downgrade() -> None:
    op.execute(
        "UPDATE organizations SET config = jsonb_set(config, '{appraisals}',"
        " (config -> 'appraisals') - 'min_goals' - 'checkin_due_days'"
        f" || jsonb_build_object('feedback_due_days', {OLD_FEEDBACK_DUE_DAYS}))"
        " WHERE jsonb_typeof(config -> 'appraisals') = 'object'"
    )
    op.execute(f"UPDATE appraisal_cycles SET feedback_due_days = {OLD_FEEDBACK_DUE_DAYS}")
    # Notes waiting on an unsent check-in have no due date; give them the old one.
    op.execute(
        "UPDATE appraisal_manager_feedback"
        f" SET due_on = period_end + {OLD_FEEDBACK_DUE_DAYS} WHERE due_on IS NULL"
    )
    op.drop_column("appraisals", "self_differently")
    op.drop_column("appraisals", "self_proud")
    op.drop_index(
        "ix_appraisal_feedback_unsent",
        table_name="appraisal_manager_feedback",
        postgresql_where="sent_at IS NULL",
    )
    op.alter_column(
        "appraisal_manager_feedback", "due_on", existing_type=sa.DATE(), nullable=False
    )
    op.drop_column("appraisal_manager_feedback", "edited_after_send_at")
    op.drop_column("appraisal_manager_feedback", "sent_at")
    op.drop_constraint("ck_appraisal_cycles_offsets", "appraisal_cycles", type_="check")
    op.create_check_constraint(
        "ck_appraisal_cycles_offsets",
        "appraisal_cycles",
        "feedback_due_days >= 0 AND hr_overdue_offset >= 0",
    )
    op.drop_column("appraisal_cycles", "checkin_due_days")
    op.drop_index(
        "ix_appraisal_check_ins_unsent",
        table_name="appraisal_check_ins",
        postgresql_where="sent_at IS NULL",
    )
    op.drop_column("appraisal_check_ins", "edited_after_send_at")
    op.drop_column("appraisal_check_ins", "sent_at")
    op.drop_column("appraisal_check_ins", "due_on")
