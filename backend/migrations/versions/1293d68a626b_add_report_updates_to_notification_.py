"""add_report_updates_to_notification_preferences

Revision ID: 1293d68a626b
Revises: 75cf31e57fdb
Create Date: 2026-06-01 13:48:36.668895

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '1293d68a626b'
down_revision = '75cf31e57fdb'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "notification_preferences",
        sa.Column(
            "report_updates",
            sa.Boolean(),
            server_default="true",
            nullable=False,
        ),
    )


def downgrade():
    op.drop_column("notification_preferences", "report_updates")
