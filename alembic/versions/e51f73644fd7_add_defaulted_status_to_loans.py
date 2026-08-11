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
    connection = op.get_bind()
    defaulted_count = connection.execute(
        sa.text("SELECT COUNT(*) FROM loans WHERE status = 'defaulted'")
    ).scalar()
    if defaulted_count:
        raise RuntimeError(
            f"{defaulted_count}개의 loans 행이 status='defaulted' 상태라 downgrade할 수 없습니다. "
            "'defaulted'인 대출을 다른 상태로 먼저 정리한 뒤 다시 시도하세요."
        )

    op.alter_column(
        'loans',
        'status',
        existing_type=sa.Enum('active', 'completed', 'defaulted'),
        type_=sa.Enum('active', 'completed'),
        existing_nullable=False,
        existing_server_default='active',
    )
