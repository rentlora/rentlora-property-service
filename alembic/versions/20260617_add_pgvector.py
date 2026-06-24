"""Add pgvector extension and embedding column

Revision ID: add_pgvector
Revises: add_performance_indexes
Create Date: 2026-06-17 12:45:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector

# revision identifiers, used by Alembic.
revision: str = 'add_pgvector'
down_revision: Union[str, None] = 'add_performance_indexes'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create the pgvector extension
    op.execute('CREATE EXTENSION IF NOT EXISTS vector;')

    # 2. Add the embedding column
    op.add_column('properties', sa.Column('embedding', Vector(1024), nullable=True))

    # 3. Create HNSW index for fast vector search using cosine similarity
    op.execute('CREATE INDEX idx_properties_embedding ON properties USING hnsw (embedding vector_cosine_ops);')


def downgrade() -> None:
    # 1. Drop the index
    op.execute('DROP INDEX IF EXISTS idx_properties_embedding;')

    # 2. Drop the column
    op.drop_column('properties', 'embedding')

    # 3. Drop the extension
    op.execute('DROP EXTENSION IF EXISTS vector;')
