"""defense_session_persona_id_to_persona_ids

Revision ID: c57befdb069e
Revises: 5f310be132ee
Create Date: 2026-04-14 21:32:39.567943

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c57befdb069e'
down_revision: Union[str, Sequence[str], None] = '5f310be132ee'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Step 1: add nullable persona_ids column
    op.add_column('defense_sessions', sa.Column('persona_ids', sa.JSON(), nullable=True, comment='答辩官 Persona ID 列表 (1-5)'))
    # Step 2: migrate data – wrap existing persona_id string into a JSON array
    op.execute("UPDATE defense_sessions SET persona_ids = json_array(persona_id) WHERE persona_id IS NOT NULL")
    # Step 3: make non-nullable and drop old column (SQLite batch mode required)
    with op.batch_alter_table('defense_sessions', schema=None) as batch_op:
        batch_op.alter_column('persona_ids', nullable=False)
        batch_op.drop_column('persona_id')


def downgrade() -> None:
    """Downgrade schema."""
    # Step 1: re-add nullable persona_id column
    with op.batch_alter_table('defense_sessions', schema=None) as batch_op:
        batch_op.add_column(sa.Column('persona_id', sa.String(length=100), nullable=True))
    # Step 2: migrate data – extract first element of persona_ids array
    op.execute("UPDATE defense_sessions SET persona_id = json_extract(persona_ids, '$[0]')")
    # Step 3: make non-nullable and drop persona_ids column
    with op.batch_alter_table('defense_sessions', schema=None) as batch_op:
        batch_op.alter_column('persona_id', nullable=False)
        batch_op.drop_column('persona_ids')
