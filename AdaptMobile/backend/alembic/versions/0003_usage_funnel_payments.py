"""Uso, embudo de conversión y estructura de pagos

Revision ID: 0003_usage_funnel_payments
Revises: 0002_region_columns
Create Date: 2026-10-09

- usage_events: un registro por crédito consumido (análisis o pregunta).
- funnel_events: pasos del embudo (register, upload_started, analysis_done...).
- payments + columnas de Stripe en users/subscriptions (sin cobrar todavía).
"""
import sqlalchemy as sa
from alembic import op

revision = "0003_usage_funnel_payments"
down_revision = "0002_region_columns"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "usage_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("action", sa.String(20), nullable=False),
        sa.Column("analysis_id", sa.Integer(), sa.ForeignKey("analyses.id", ondelete="SET NULL"), nullable=True),
        sa.Column("credits_spent", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    for col in ("user_id", "action", "analysis_id", "created_at"):
        op.create_index(f"ix_usage_events_{col}", "usage_events", [col])

    op.create_table(
        "funnel_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("event", sa.String(30), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    for col in ("user_id", "event", "created_at"):
        op.create_index(f"ix_funnel_events_{col}", "funnel_events", [col])

    op.create_table(
        "payments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("subscription_id", sa.Integer(), sa.ForeignKey("subscriptions.id", ondelete="SET NULL"), nullable=True),
        sa.Column("provider", sa.String(30), nullable=False, server_default=sa.text("'stripe'")),
        sa.Column("provider_payment_id", sa.String(255), nullable=True),
        sa.Column("amount", sa.Float(), nullable=True),
        sa.Column("currency", sa.String(3), nullable=False, server_default=sa.text("'usd'")),
        sa.Column("status", sa.String(30), nullable=False, server_default=sa.text("'pending'")),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_payments_user_id", "payments", ["user_id"])
    op.create_index("ix_payments_provider_payment_id", "payments", ["provider_payment_id"])

    # Columnas de Stripe (vacías hasta activar los pagos reales)
    op.add_column("users", sa.Column("stripe_customer_id", sa.String(255), nullable=True))
    op.create_index("ix_users_stripe_customer_id", "users", ["stripe_customer_id"])
    op.add_column("subscriptions", sa.Column("stripe_price_id", sa.String(255), nullable=True))


def downgrade() -> None:
    op.drop_index("ix_users_stripe_customer_id", table_name="users")
    op.drop_column("users", "stripe_customer_id")
    op.drop_column("subscriptions", "stripe_price_id")
    op.drop_table("payments")
    op.drop_table("funnel_events")
    op.drop_table("usage_events")
