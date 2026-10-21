"""Columnas de región y antigüedad en devices/analyses

Revision ID: 0002_region_columns
Revises: 0001_initial
Create Date: 2026-10-09

Equivale al antiguo `ensure_region_schema()` (ALTER TABLE ... IF NOT EXISTS) pero
en Alembic y de forma idempotente: si una base ya tenía las columnas (por ejemplo
la creada por la versión anterior con `create_all` + ALTERs), esta migración no
hace nada. Por eso el arranque comprueba el esquema y "estampa" 0001 cuando la
base ya existía: 0002 se encarga de completar lo que falte sin romper nada.
"""
import sqlalchemy as sa
from alembic import op

revision = "0002_region_columns"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def _columns(table: str) -> set:
    insp = sa.inspect(op.get_bind())
    if not insp.has_table(table):
        return set()
    return {c["name"] for c in insp.get_columns(table)}


def _indexes(table: str) -> set:
    insp = sa.inspect(op.get_bind())
    if not insp.has_table(table):
        return set()
    return {i["name"] for i in insp.get_indexes(table)}


def upgrade() -> None:
    wanted = [
        ("devices", "in_mx", sa.Boolean(), sa.text("false"), False),
        ("devices", "in_us", sa.Boolean(), sa.text("false"), False),
        ("devices", "in_ca", sa.Boolean(), sa.text("false"), False),
        ("devices", "region_basis", sa.JSON(), None, True),
        ("devices", "is_legacy", sa.Boolean(), sa.text("false"), False),
        ("analyses", "region", sa.String(5), sa.text("'mx'"), True),
    ]
    for table, column, type_, default, nullable in wanted:
        if column in _columns(table):
            continue
        op.add_column(table, sa.Column(column, type_, nullable=nullable, server_default=default))

    for name, table, cols in [
        ("ix_devices_is_legacy", "devices", ["is_legacy"]),
        ("ix_devices_in_mx", "devices", ["in_mx"]),
        ("ix_devices_in_us", "devices", ["in_us"]),
        ("ix_devices_in_ca", "devices", ["in_ca"]),
    ]:
        if name not in _indexes(table):
            op.create_index(name, table, cols)


def downgrade() -> None:
    for name, table in [
        ("ix_devices_in_ca", "devices"),
        ("ix_devices_in_us", "devices"),
        ("ix_devices_in_mx", "devices"),
        ("ix_devices_is_legacy", "devices"),
    ]:
        if name in _indexes(table):
            op.drop_index(name, table_name=table)
    for table, column in [
        ("analyses", "region"),
        ("devices", "is_legacy"),
        ("devices", "region_basis"),
        ("devices", "in_ca"),
        ("devices", "in_us"),
        ("devices", "in_mx"),
    ]:
        if column in _columns(table):
            op.drop_column(table, column)
