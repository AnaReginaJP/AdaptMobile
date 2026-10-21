"""Esquema inicial (versión previa a regiones)

Revision ID: 0001_initial
Revises:
Create Date: 2026-10-09

Refleja el esquema tal como existía antes de esta entrega: usuarios, dispositivos,
análisis, dispositivos evaluados, preguntas y planes. Las columnas de región
llegan en 0002 y las de uso/pagos en 0003.

Nota: no se recrean índices redundantes sobre claves primarias (el PK ya indexa);
el resto de índices coincide con los `index=True` de app/models.py.
"""
from alembic import op
import sqlalchemy as sa

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column("full_name", sa.String(255), nullable=True),
        sa.Column("role", sa.String(50), nullable=True),
        sa.Column("plan", sa.String(50), nullable=True),
        sa.Column("credits_limit", sa.Integer(), nullable=True),
        sa.Column("credits_used", sa.Integer(), nullable=True),
        sa.Column("period_start", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    op.create_table(
        "devices",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("phone_brand", sa.String(100), nullable=False),
        sa.Column("phone_model", sa.String(255), nullable=False),
        sa.Column("ram_gb", sa.Float(), nullable=True),
        sa.Column("storage_gb", sa.Float(), nullable=True),
        sa.Column("os_type", sa.String(50), nullable=True),
        sa.Column("os_version", sa.String(100), nullable=True),
        sa.Column("os_version_num", sa.Float(), nullable=True),
        sa.Column("cpu", sa.Text(), nullable=True),
        sa.Column("cpu_cores", sa.Integer(), nullable=True),
        sa.Column("gpu", sa.Text(), nullable=True),
        sa.Column("gpu_company", sa.String(100), nullable=True),
        sa.Column("chipset", sa.Text(), nullable=True),
        sa.Column("display_resolution", sa.String(100), nullable=True),
        sa.Column("ppi_density", sa.Integer(), nullable=True),
        sa.Column("battery_size", sa.String(50), nullable=True),
        sa.Column("price_usd", sa.Float(), nullable=True),
        sa.Column("price_range", sa.String(50), nullable=True),
        sa.Column("release_year", sa.Integer(), nullable=True),
        sa.Column("raw_specs", sa.JSON(), nullable=True),
        sa.UniqueConstraint("phone_brand", "phone_model", "ram_gb", "storage_gb",
                            name="uq_device_brand_model_ram_storage"),
    )
    for col in ("phone_brand", "phone_model", "ram_gb", "os_type", "os_version_num"):
        op.create_index(f"ix_devices_{col}", "devices", [col])

    op.create_table(
        "analyses",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("filename", sa.String(255), nullable=False),
        sa.Column("file_type", sa.String(50), nullable=True),
        sa.Column("project_name", sa.String(255), nullable=False),
        sa.Column("tech_stack", sa.JSON(), nullable=True),
        sa.Column("requirements", sa.JSON(), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("recommendations", sa.JSON(), nullable=True),
        sa.Column("stats", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )

    op.create_table(
        "analysis_devices",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("analysis_id", sa.Integer(), sa.ForeignKey("analyses.id", ondelete="CASCADE"), nullable=False),
        sa.Column("device_id", sa.Integer(), sa.ForeignKey("devices.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", sa.String(50), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
    )

    op.create_table(
        "questions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("analysis_id", sa.Integer(), sa.ForeignKey("analyses.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("device_name", sa.String(255), nullable=True),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("answer", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )

    op.create_table(
        "subscriptions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(50), nullable=False, unique=True),
        sa.Column("monthly_credits", sa.Integer(), nullable=False),
        sa.Column("price_usd", sa.Float(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("features", sa.JSON(), nullable=True),
    )


def downgrade() -> None:
    for table in ("subscriptions", "questions", "analysis_devices", "analyses", "devices", "users"):
        op.drop_table(table)
