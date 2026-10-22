"""Initial billing schema.

Revision ID: 20261022_initial_billing_schema
Revises: None
Create Date: 2026-10-22 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

revision = "20261022_initial_billing_schema"
down_revision = None
branch_labels = None
deps = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("full_name", sa.String(length=255), nullable=True),
        sa.Column("country_code", sa.String(length=10), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_users_email"), "users", ["email"], unique=True)

    op.create_table(
        "wallets",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("currency", sa.String(length=8), nullable=False),
        sa.Column("balance_credits", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id"),
        sa.CheckConstraint("balance_credits >= 0", name="wallet_balance_non_negative"),
    )

    op.create_table(
        "credit_packages",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("currency", sa.String(length=8), nullable=False),
        sa.Column("price_cents", sa.Integer(), nullable=False),
        sa.Column("credit_units", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code"),
        sa.CheckConstraint("price_cents >= 0", name="credit_package_price_non_negative"),
        sa.CheckConstraint("credit_units > 0", name="credit_package_credit_units_positive"),
    )
    op.create_index(op.f("ix_credit_packages_code"), "credit_packages", ["code"], unique=True)

    op.create_table(
        "payment_transactions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("provider", sa.String(length=64), nullable=False),
        sa.Column("provider_payment_id", sa.String(length=255), nullable=True),
        sa.Column("provider_session_id", sa.String(length=255), nullable=True),
        sa.Column("currency", sa.String(length=8), nullable=False),
        sa.Column("amount_cents", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("paid_cents", sa.Integer(), nullable=False),
        sa.Column("provider_metadata", sa.JSON(), nullable=True),
        sa.Column("idempotency_key", sa.String(length=255), nullable=True),
        sa.Column("webhook_event_id", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint("amount_cents >= 0", name="payment_transaction_amount_non_negative"),
        sa.CheckConstraint("paid_cents >= 0", name="payment_transaction_paid_non_negative"),
    )
    op.create_index(op.f("ix_payment_transactions_idempotency_key"), "payment_transactions", ["idempotency_key"], unique=True)
    op.create_index(op.f("ix_payment_transactions_provider_payment_id"), "payment_transactions", ["provider_payment_id"], unique=False)
    op.create_index(op.f("ix_payment_transactions_provider_session_id"), "payment_transactions", ["provider_session_id"], unique=False)
    op.create_index(op.f("ix_payment_transactions_webhook_event_id"), "payment_transactions", ["webhook_event_id"], unique=True)

    op.create_table(
        "credit_ledger_entries",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("wallet_id", sa.Integer(), nullable=True),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("payment_transaction_id", sa.Integer(), nullable=True),
        sa.Column("entry_type", sa.String(length=32), nullable=False),
        sa.Column("amount_credits", sa.Integer(), nullable=False),
        sa.Column("currency", sa.String(length=8), nullable=False),
        sa.Column("reason", sa.String(length=255), nullable=False),
        sa.Column("extra_data", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["payment_transaction_id"], ["payment_transactions.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["wallet_id"], ["wallets.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint("amount_credits != 0", name="credit_ledger_entry_amount_non_zero"),
    )
    op.create_index(op.f("ix_credit_ledger_entries_user_id"), "credit_ledger_entries", ["user_id"], unique=False)
    op.create_index(op.f("ix_credit_ledger_entries_wallet_id"), "credit_ledger_entries", ["wallet_id"], unique=False)

    op.create_table(
        "generation_requests",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("request_key", sa.String(length=255), nullable=False),
        sa.Column("doc_type", sa.String(length=64), nullable=False),
        sa.Column("input_hash", sa.String(length=255), nullable=False),
        sa.Column("response_payload", sa.JSON(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_generation_requests_request_key"), "generation_requests", ["request_key"], unique=True)
    op.create_index(op.f("ix_generation_requests_user_id"), "generation_requests", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_generation_requests_user_id"), table_name="generation_requests")
    op.drop_index(op.f("ix_generation_requests_request_key"), table_name="generation_requests")
    op.drop_table("generation_requests")
    op.drop_index(op.f("ix_credit_ledger_entries_wallet_id"), table_name="credit_ledger_entries")
    op.drop_index(op.f("ix_credit_ledger_entries_user_id"), table_name="credit_ledger_entries")
    op.drop_table("credit_ledger_entries")
    op.drop_index(op.f("ix_payment_transactions_webhook_event_id"), table_name="payment_transactions")
    op.drop_index(op.f("ix_payment_transactions_provider_session_id"), table_name="payment_transactions")
    op.drop_index(op.f("ix_payment_transactions_provider_payment_id"), table_name="payment_transactions")
    op.drop_index(op.f("ix_payment_transactions_idempotency_key"), table_name="payment_transactions")
    op.drop_table("payment_transactions")
    op.drop_index(op.f("ix_credit_packages_code"), table_name="credit_packages")
    op.drop_table("credit_packages")
    op.drop_table("wallets")
    op.drop_index(op.f("ix_users_email"), table_name="users")
    op.drop_table("users")
