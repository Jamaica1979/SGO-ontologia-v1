"""posiciones de puesto, campos de ficha, formularios del puesto y traspasos (v3.9)

Revision ID: 7c3e91b2a5d4
Revises: 186adf90f69d
Create Date: 2026-10-20
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '7c3e91b2a5d4'
down_revision: Union[str, Sequence[str], None] = '186adf90f69d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

CAMPOS_PUESTO = ("dotacion", "reemplaza_a", "alcance_inicio", "alcance_fin", "equipos",
                 "medicion_desempeno", "notas_ficha")


def upgrade() -> None:
    # SQLite: ADD COLUMN simple (nullable, sin tocar datos existentes)
    for col in CAMPOS_PUESTO:
        op.add_column('puestos', sa.Column(col, sa.Text(), nullable=True))
    op.add_column('actividades', sa.Column('posicion', sa.Text(), nullable=True))
    op.add_column('actividades', sa.Column('momento', sa.Text(), nullable=True))
    op.add_column('actividades', sa.Column('orden', sa.Integer(), nullable=True))

    op.create_table(
        'posiciones',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('puesto_codigo', sa.Text(), sa.ForeignKey('puestos.codigo'), nullable=False),
        sa.Column('clave', sa.Text(), nullable=False),
        sa.Column('nombre', sa.Text(), nullable=False),
        sa.Column('orden', sa.Integer(), server_default='0'),
        sa.Column('descripcion', sa.Text()),
        sa.Column('alcance_inicio', sa.Text()),
        sa.Column('alcance_fin', sa.Text()),
        sa.Column('equipos', sa.Text()),
        sa.Column('activo', sa.Integer(), server_default='1'),
        sa.Column('created_at', sa.Text(), server_default=sa.text("(datetime('now'))")),
        sa.UniqueConstraint('puesto_codigo', 'clave'),
    )
    op.create_table(
        'traspasos',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('de_puesto_codigo', sa.Text(), sa.ForeignKey('puestos.codigo')),
        sa.Column('de_texto', sa.Text()),
        sa.Column('a_puesto_codigo', sa.Text(), sa.ForeignKey('puestos.codigo')),
        sa.Column('a_texto', sa.Text()),
        sa.Column('que_entrega', sa.Text(), nullable=False),
        sa.Column('senal', sa.Text()),
        sa.Column('orden', sa.Integer(), server_default='0'),
        sa.Column('created_at', sa.Text(), server_default=sa.text("(datetime('now'))")),
    )
    op.create_table(
        'puesto_formularios',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('puesto_codigo', sa.Text(), sa.ForeignKey('puestos.codigo'), nullable=False),
        sa.Column('formulario_id', sa.Integer(), sa.ForeignKey('formularios.id'), nullable=False),
        sa.Column('rol', sa.Text(), server_default='completa'),
        sa.Column('para_que', sa.Text()),
        sa.Column('cuando', sa.Text()),
        sa.Column('orden', sa.Integer(), server_default='0'),
        sa.UniqueConstraint('puesto_codigo', 'formulario_id', 'rol'),
    )


def downgrade() -> None:
    op.drop_table('puesto_formularios')
    op.drop_table('traspasos')
    op.drop_table('posiciones')
    with op.batch_alter_table('actividades') as b:
        for col in ('orden', 'momento', 'posicion'):
            b.drop_column(col)
    with op.batch_alter_table('puestos') as b:
        for col in reversed(CAMPOS_PUESTO):
            b.drop_column(col)
