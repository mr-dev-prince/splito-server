"""update group member table

Revision ID: 9c931b4c6df9
Revises: f37779ecb315
Create Date: 2026-01-07 22:27:55.298919

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9c931b4c6df9'
down_revision: Union[str, Sequence[str], None] = 'f37779ecb315'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_table('group_members')

    op.create_table(
        'group_members',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('group_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=True),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('email', sa.String(), nullable=True),
        sa.Column('phone', sa.String(), nullable=True),
        sa.Column('joined_at', sa.DateTime(), server_default=sa.func.now()),

        sa.ForeignKeyConstraint(
            ['group_id'],
            ['groups.id'],
            ondelete='CASCADE',
        ),
        sa.ForeignKeyConstraint(
            ['user_id'],
            ['users.id'],
            ondelete='SET NULL',
        ),

        sa.UniqueConstraint('group_id', 'email', name='uq_group_member_email'),
        sa.UniqueConstraint('group_id', 'phone', name='uq_group_member_phone'),
    )

def downgrade() -> None:
    op.drop_table('group_members')
