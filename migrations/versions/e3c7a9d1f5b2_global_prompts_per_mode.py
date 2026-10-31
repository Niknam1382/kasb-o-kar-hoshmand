"""global AI prompts per business mode (P1-S2)

Revision ID: e3c7a9d1f5b2
Revises: c1a5e0d7b3f2
Create Date: 2026-10-23 01:00:00.000000

فازِ ۱ · P1-S2 (J1): AdminSettings.global_ai_prompt_sales / global_ai_prompt_consultation (Text، nullable).
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "e3c7a9d1f5b2"
down_revision: Union[str, Sequence[str], None] = "c1a5e0d7b3f2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("admin_settings", sa.Column("global_ai_prompt_sales", sa.Text(), nullable=True))
    op.add_column("admin_settings", sa.Column("global_ai_prompt_consultation", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("admin_settings", "global_ai_prompt_consultation")
    op.drop_column("admin_settings", "global_ai_prompt_sales")
