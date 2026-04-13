"""drop v1 legacy columns

Revision ID: b3c7f2a1d456
Revises: ac7fa9a4e143
Create Date: 2026-04-13 18:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b3c7f2a1d456'
down_revision: Union[str, Sequence[str], None] = 'ac7fa9a4e143'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Drop v1 legacy columns: full_content, legacy_content, schema_version."""
    with op.batch_alter_table('stakeholder_personas', schema=None) as batch_op:
        batch_op.drop_index('ix_stakeholder_personas_schema_version')
        batch_op.drop_column('full_content')
        batch_op.drop_column('legacy_content')
        batch_op.drop_column('schema_version')


def downgrade() -> None:
    """Re-add v1 legacy columns."""
    with op.batch_alter_table('stakeholder_personas', schema=None) as batch_op:
        batch_op.add_column(
            sa.Column('full_content', sa.Text(), server_default='', nullable=False,
                       comment='v1 markdown 全文')
        )
        batch_op.add_column(
            sa.Column('schema_version', sa.Integer(), server_default='1', nullable=False,
                       comment='schema 版本: 1=legacy markdown, 2=structured')
        )
        batch_op.add_column(
            sa.Column('legacy_content', sa.Text(), nullable=True,
                       comment='迁移前 markdown 原文备份')
        )
        batch_op.create_index('ix_stakeholder_personas_schema_version', ['schema_version'],
                              unique=False)
