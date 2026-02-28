"""add_truck_type_and_perishability

Revision ID: a1b2c3d4e5f6
Revises: 5720e6e42c6a
Create Date: 2026-02-28 14:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = '5720e6e42c6a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create the truck_type enum type — idempotent in case it survived a DB reset
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE truck_type_enum AS ENUM ('REEFER', 'VENTILATED', 'INSULATED', 'DRY_VAN');
        EXCEPTION
            WHEN duplicate_object THEN NULL;
        END $$;
    """)

    # Add truck_type to middlemen — default existing rows to DRY_VAN
    op.add_column(
        'middlemen',
        sa.Column(
            'truck_type',
            sa.Enum('REEFER', 'VENTILATED', 'INSULATED', 'DRY_VAN', name='truck_type_enum'),
            nullable=False,
            server_default='DRY_VAN',
        ),
    )
    # Remove server_default — application supplies the value going forward
    op.alter_column('middlemen', 'truck_type', server_default=None)

    # Add perishability fields to orders
    op.add_column(
        'orders',
        sa.Column(
            'requires_cold_chain',
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    op.alter_column('orders', 'requires_cold_chain', server_default=None)

    op.add_column(
        'orders',
        sa.Column('harvest_date', sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column('orders', 'harvest_date')
    op.drop_column('orders', 'requires_cold_chain')
    op.drop_column('middlemen', 'truck_type')
    op.execute("DROP TYPE truck_type_enum")
