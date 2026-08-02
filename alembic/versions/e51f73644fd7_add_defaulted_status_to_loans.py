"""add defaulted status to loans

Revision ID: e51f73644fd7
Revises: 261ebc5ee393
Create Date: 2026-08-02 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e51f73644fd7'
down_revision: Union[str, Sequence[str], None] = '261ebc5ee393'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.alter_column(
        'loans',
        'status',
        existing_type=sa.Enum('active', 'completed'),
        type_=sa.Enum('active', 'completed', 'defaulted'),
        existing_nullable=False,
        existing_server_default='active',
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.alter_column(
        'loans',
        'status',
        existing_type=sa.Enum('active', 'completed', 'defaulted'),
        type_=sa.Enum('active', 'completed'),
        existing_nullable=False,
        existing_server_default='active',
    )
