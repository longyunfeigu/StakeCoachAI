"""add stakeholder_analysis_reports table

Revision ID: ad572d1348de
Revises: 074e129df5d5
Create Date: 2026-04-04 20:49:29.277390

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'ad572d1348de'
down_revision: Union[str, Sequence[str], None] = '074e129df5d5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('stakeholder_analysis_reports',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False, comment='主键ID'),
    sa.Column('room_id', sa.Integer(), nullable=False, comment='所属聊天室ID'),
    sa.Column('summary', sa.Text(), nullable=False, comment='分析摘要'),
    sa.Column('content', sa.JSON(), nullable=False, comment='完整报告结构体'),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False, comment='生成时间'),
    sa.ForeignKeyConstraint(['room_id'], ['stakeholder_chat_rooms.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    comment='利益相关者对话分析报告'
    )
    with op.batch_alter_table('stakeholder_analysis_reports', schema=None) as batch_op:
        batch_op.create_index('ix_stakeholder_analysis_reports_room_id', ['room_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('stakeholder_analysis_reports', schema=None) as batch_op:
        batch_op.drop_index('ix_stakeholder_analysis_reports_room_id')

    op.drop_table('stakeholder_analysis_reports')
