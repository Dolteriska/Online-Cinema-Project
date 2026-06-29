"""seed_user_groups

Revision ID: d10a5f8cf9f6
Revises: c3fda853efaa
Create Date: 2026-06-24 16:10:07.575554

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

from sqlalchemy.sql import table, column

# revision identifiers, used by Alembic.
revision: str = 'd10a5f8cf9f6'
down_revision: Union[str, Sequence[str], None] = 'c3fda853efaa'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    user_group_enum = sa.Enum("USER", "MODERATOR", "ADMIN", name="usergroupenum")
    user_groups_table = table(
        'user_groups',
        column('id', sa.Integer),
        column('name', user_group_enum)
    )

    op.bulk_insert(
        user_groups_table,
        [
            {'id': 1, 'name': 'USER'},
            {'id': 2, 'name': 'MODERATOR'},
            {'id': 3, 'name': 'ADMIN'},
        ]
    )


def downgrade() -> None:
    op.execute("DELETE FROM user_groups WHERE name IN ('user', 'moderator', 'admin')")
