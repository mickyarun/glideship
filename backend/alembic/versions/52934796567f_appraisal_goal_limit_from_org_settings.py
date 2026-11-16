"""appraisal goal limit from org settings

The number of confirmed goals per period moves from a fixed three to the
org's appraisal settings, so goal slots are only bounded below. Autogenerate
doesn't compare check constraints, so the swap is spelled out here.

Revision ID: 52934796567f
Revises: 172dace6afc9
Create Date: 2026-11-16 17:32:49.784934

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "52934796567f"
down_revision: str | None = "172dace6afc9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint("ck_appraisal_goals_position", "appraisal_goals", type_="check")
    op.create_check_constraint("ck_appraisal_goals_position", "appraisal_goals", "position >= 1")


def downgrade() -> None:
    op.drop_constraint("ck_appraisal_goals_position", "appraisal_goals", type_="check")
    op.create_check_constraint(
        "ck_appraisal_goals_position", "appraisal_goals", "position BETWEEN 1 AND 3"
    )
