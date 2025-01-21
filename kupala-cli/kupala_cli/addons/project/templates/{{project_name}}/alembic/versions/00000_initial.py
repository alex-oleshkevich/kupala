"""Base revision

This is a special revision that plays a role of "base" revision.
You can reset your database to this state by running:
`alembic downgrade base`.

Revision ID: 9223d07a31d3
Revises:
Create Date: 2024-11-02 18:13:25.998428

"""

# revision identifiers, used by Alembic.
revision = "initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
