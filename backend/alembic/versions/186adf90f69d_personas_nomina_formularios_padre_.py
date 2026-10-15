"""personas nomina, formularios padre, exclusiones planta

Revision ID: 186adf90f69d
Revises: 4afec79fdaed
Create Date: 2026-10-13
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '186adf90f69d'
down_revision: Union[str, Sequence[str], None] = '4afec79fdaed'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # SQLite: ADD COLUMN simple (nullable, sin tocar datos existentes)
    for col in ("apodo", "fecha_ingreso", "sector", "cargo_nomina"):
        op.add_column('personas', sa.Column(col, sa.Text(), nullable=True))
    op.add_column('personas', sa.Column('planta_base_id', sa.Integer(), nullable=True))
    op.add_column('formularios', sa.Column('formulario_padre_id', sa.Integer(), nullable=True))
    op.add_column('formularios', sa.Column('estructura', sa.Text(), nullable=True))
    op.create_table('exclusiones_planta',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('planta_id', sa.Integer(), nullable=False),
        sa.Column('puesto_codigo', sa.Text(), nullable=True),
        sa.Column('actividad_id', sa.Integer(), nullable=True),
        sa.Column('se_reparte', sa.Integer(), server_default='0', nullable=True),
        sa.Column('motivo', sa.Text(), nullable=True),
        sa.Column('created_at', sa.Text(), server_default=sa.text("(datetime('now'))"), nullable=True),
        sa.ForeignKeyConstraint(['actividad_id'], ['actividades.id']),
        sa.ForeignKeyConstraint(['planta_id'], ['plantas.id']),
        sa.ForeignKeyConstraint(['puesto_codigo'], ['puestos.codigo']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('planta_id', 'puesto_codigo', 'actividad_id'))


def downgrade() -> None:
    op.drop_table('exclusiones_planta')
