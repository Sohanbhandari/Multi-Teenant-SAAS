"""${message}

Revision ID: ${up_revision}
Revises: ${down_revision | comma,n}
Create Date: ${create_date}

MANDATORY ARCHITECTURE REMINDERS:
- If this migration creates a tenant-owned table, verify it includes:
    * id (UUID PK)
    * organization_id (UUID FK NOT NULL, indexed)
    * created_at (TIMESTAMPTZ NOT NULL DEFAULT now())
    * updated_at (TIMESTAMPTZ NOT NULL DEFAULT now())
    * created_by (UUID FK -> users.id)
    * updated_by (UUID FK -> users.id)
    * status (VARCHAR(50) NOT NULL DEFAULT 'active', indexed)
- Tenant uniqueness must be composite: UniqueConstraint('organization_id', 'slug', ...)
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
${imports if imports else ""}

# revision identifiers, used by Alembic.
revision: str = ${repr(up_revision)}
down_revision: Union[str, None] = ${repr(down_revision)}
branch_labels: Union[str, Sequence[str], None] = ${repr(branch_labels)}
depends_on: Union[str, Sequence[str], None] = ${repr(depends_on)}


def upgrade() -> None:
    ${upgrades if upgrades else "pass"}


def downgrade() -> None:
    ${downgrades if downgrades else "pass"}

