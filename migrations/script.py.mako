"""Initial billing models and ledger tables.

Revision ID: 20261022_initial_billing_schema
Revises: None
Create Date: 2026-10-22 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
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
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email"),
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
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
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


def downgrade() -> None:
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


migrations/versions/20261022_initial_billing_schema.py
"""Initial billing models and ledger tables.

Revision ID: 20261022_initial_billing_schema
Revises: None
Create Date: 2026-10-22 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
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
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email"),
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
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
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


def downgrade() -> None:
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


migrations/script.py.mako
"""${message}

Revision ID: ${up_revision}
Revises: ${down_revision | comma,n}
Create Date: ${create_date}

"""
from alembic import op
import sqlalchemy as sa
${imports if imports else ""}

# revision identifiers, used by Alembic.
revision = ${repr(up_revision)}
down_revision = ${repr(down_revision)}
branch_labels = ${repr(branch_labels)}
deps = ${repr(deps)}


def upgrade() -> None:
    ${upgrades if upgrades else "pass"}


def downgrade() -> None:
    ${downgrades if downgrades else "pass"}


pytest.ini
[pytest]
testpaths = tests


tests/conftest.py
import pytest
from flask import Flask

from app import create_app


@pytest.fixture()
def app():
    app = create_app(test_config={"TESTING": True, "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:"})
    app.config["SERVER_NAME"] = "localhost"
    with app.app_context():
        from extensions import db
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture()
def client(app):
    return app.test_client()


tests/test_billing_foundation.py
from extensions import db
from models import CreditLedgerEntry, PaymentTransaction, User, Wallet, get_or_create_wallet


def test_app_initializes_with_test_database(app):
    assert app is not None
    assert app.config["TESTING"] is True
    assert "users" in db.metadata.tables
    assert "wallets" in db.metadata.tables
    assert "payment_transactions" in db.metadata.tables
    assert "credit_ledger_entries" in db.metadata.tables


def test_wallet_balance_and_ledger_integrity(app):
    with app.app_context():
        user = User(email="wallet@example.com", full_name="Wallet User")
        db.session.add(user)
        db.session.commit()

        wallet = get_or_create_wallet(user.id, currency="KES")
        wallet.add_credits(100, "initial credit", user=user)
        db.session.commit()
        assert wallet.balance_credits == 100

        wallet.spend_credits(40, "document generation", user=user)
        db.session.commit()
        assert wallet.balance_credits == 60

        ledger = CreditLedgerEntry.query.filter_by(user_id=user.id).all()
        assert len(ledger) == 2
        assert sum(entry.amount_credits for entry in ledger) == 60


def test_duplicate_payment_transaction_idempotency_is_protected(app):
    with app.app_context():
        user = User(email="pay@example.com", full_name="Pay User")
        db.session.add(user)
        db.session.commit()

        payment = PaymentTransaction(
            user_id=user.id,
            provider="stripe",
            currency="KES",
            amount_cents=5000,
            status="succeeded",
            paid_cents=5000,
            provider_metadata={"status": "succeeded"},
            idempotency_key="same-key",
        )
        db.session.add(payment)
        db.session.commit()

        duplicate = PaymentTransaction(
            user_id=user.id,
            provider="stripe",
            currency="KES",
            amount_cents=5000,
            status="succeeded",
            paid_cents=5000,
            provider_metadata={"status": "succeeded"},
            idempotency_key="same-key",
        )
        db.session.add(duplicate)
        try:
            db.session.commit()
        except Exception:
            db.session.rollback()
            assert True
        else:
            assert False, "Expected duplicate idempotency key to be rejected."


app.py
import json
import os

from flask import Flask, Response, jsonify, render_template, request
from openai import OpenAI

from config import config
from extensions import db, migrate
from models import User, Wallet  # noqa: F401


SYSTEM_PROMPTS = {
    "resume": "You are an expert resume writer. Parse the user's input and return a JSON object with these fields:\n{\n  \"name\": \"\", \"email\": \"\", \"phone\": \"\", \"location\": \"\", \"linkedin\": \"\", \"website\": \"\", \"summary\": \"\", \"skills\": [], \"languages\": [], \"experience\": [], \"education\": [], \"certifications\": [], \"projects\": []\n}\n",
    "cv": "You are an expert CV writer. Return valid JSON with personal info, summary, skills, experience, education, languages, and certs.",
    "academic_cv": "You are a professional academic CV writer. Return valid JSON with personal info, research, teaching, publications, and education.",
    "cover_letter": "You are a professional cover letter writer. Return valid JSON containing a subject and a full_letter field.",
    "portfolio": "You are a portfolio writer. Return valid JSON with personal info, bio, skills, projects, education, and achievements.",
    "org_letter": "You are a formal letter writer. Return valid JSON with a subject and a full_letter field.",
}

REPLY_MESSAGES = {
    "resume": "Your resume has been generated! You can see it in the preview. Switch templates or edit the form to refine it.",
    "cv": "Your CV is ready in the preview panel. Feel free to refine it.",
    "academic_cv": "Your academic CV is ready in the preview panel.",
    "cover_letter": "Your cover letter is ready.",
    "portfolio": "Your portfolio is ready.",
    "org_letter": "Your formal letter is ready.",
}


def create_app(test_config=None):
    app = Flask(__name__)
    app.config.from_object(config)
    if test_config:
        app.config.update(test_config)

    db.init_app(app)
    migrate.init_app(app, db)

    @app.route("/")
    def home():
        return render_template("doccraft.html")

    @app.route("/robots.txt")
    def robots_txt():
        content = """User-agent: *
Allow: /
Disallow: /api/
Disallow: /health

Sitemap: https://doccraft-pro.onrender.com/sitemap.xml
"""
        return Response(content, mimetype="text/plain")

    @app.route("/sitemap.xml")
    def sitemap_xml():
        content = """<?xml version=\"1.0\" encoding=\"UTF-8\"?>
<urlset xmlns=\"http://www.sitemaps.org/schemas/sitemap/0.9\">
  <url>
    <loc>https://doccraft-pro.onrender.com/</loc>
  </url>
</urlset>
"""
        return Response(content, mimetype="application/xml")

    @app.route("/health")
    def health():
        return jsonify({"status": "ok", "app": "DocCraft"})

    @app.route("/api/generate", methods=["POST"])
    def generate():
        body = request.get_json(silent=True) or {}
        doc_type = body.get("doc_type", "resume")
        user_input = body.get("user_input", "")
        extra = body.get("extra") or {}

        if not isinstance(user_input, str) or not user_input.strip():
            return jsonify({"success": False, "error": "Please enter your information."}), 400

        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            return jsonify({"success": False, "error": "Generation is not configured yet."}), 503

        prompt = SYSTEM_PROMPTS.get(doc_type, SYSTEM_PROMPTS.get("resume", "Create a professional document and return valid JSON."))
        context = ""
        if isinstance(extra, dict) and extra.get("currentData"):
            context = "\n\nExisting data to merge with:\n" + json.dumps(extra["currentData"])

        try:
            client = OpenAI(api_key=api_key)
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": user_input + context},
                ],
                temperature=0.7,
                max_tokens=2000,
                response_format={"type": "json_object"},
            )
            raw = (response.choices[0].message.content or "").strip()
            if raw.startswith("```"):
                raw = raw.split("\n", 1)[-1]
                if raw.endswith("```"):
                    raw = raw[:-3]
            data = json.loads(raw.strip())
            return jsonify({
                "success": True,
                "data": data,
                "reply": REPLY_MESSAGES.get(doc_type, "Document generated successfully!"),
            })
        except Exception:
            app.logger.exception("DocCraft generation failed")
            return jsonify({"success": False, "error": "Generation failed. Please try again."}), 502

    return app


app = create_app()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "5000")))


migrations/script.py.mako
"""${message}

Revision ID: ${up_revision}
Revises: ${down_revision | comma,n}
Create Date: ${create_date}

"""
from alembic import op
import sqlalchemy as sa
${imports if imports else ""}

# revision identifiers, used by Alembic.
revision = ${repr(up_revision)}
down_revision = ${repr(down_revision)}
branch_labels = ${repr(branch_labels)}
deps = ${repr(deps)}


def upgrade() -> None:
    ${upgrades if upgrades else "pass"}


def downgrade() -> None:
    ${downgrades if downgrades else "pass"}


requirements.txt
Flask>=3.1,<4.0
openai>=1.0,<3.0
gunicorn>=22.0,<24.0
Flask-SQLAlchemy>=3.1,<4.0
Flask-Migrate>=4.0,<5.0
psycopg2-binary>=2.9,<3.0
python-dotenv>=1.0,<2.0
pytest>=8.0,<9.0


migrations/versions/20261022_initial_billing_schema.py
"""Initial billing models and ledger tables.

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
        sa.Column("is_active", sa.Boolean(), nullable=False),
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
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
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


def downgrade() -> None:
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


pytest.ini
[pytest]
testpaths = tests


tests/conftest.py
import pytest

from app import create_app


@pytest.fixture()
def app():
    app = create_app(test_config={"TESTING": True, "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:"})
    app.config["SERVER_NAME"] = "localhost"
    with app.app_context():
        from extensions import db
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture()
def client(app):
    return app.test_client()


tests/test_billing_foundation.py
from extensions import db
from models import CreditLedgerEntry, PaymentTransaction, User, get_or_create_wallet


def test_app_initializes_with_test_database(app):
    assert app is not None
    assert app.config["TESTING"] is True
    assert "users" in db.metadata.tables
    assert "wallets" in db.metadata.tables
    assert "payment_transactions" in db.metadata.tables
    assert "credit_ledger_entries" in db.metadata.tables


def test_wallet_balance_and_ledger_integrity(app):
    with app.app_context():
        user = User(email="wallet@example.com", full_name="Wallet User")
        db.session.add(user)
        db.session.commit()

        wallet = get_or_create_wallet(user.id, currency="KES")
        wallet.add_credits(100, "initial credit", user=user)
        db.session.commit()
        assert wallet.balance_credits == 100

        wallet.spend_credits(40, "document generation", user=user)
        db.session.commit()
        assert wallet.balance_credits == 60

        ledger = CreditLedgerEntry.query.filter_by(user_id=user.id).all()
        assert len(ledger) == 2
        assert sum(entry.amount_credits for entry in ledger) == 60


def test_duplicate_payment_transaction_idempotency_is_protected(app):
    with app.app_context():
        user = User(email="pay@example.com", full_name="Pay User")
        db.session.add(user)
        db.session.commit()

        payment = PaymentTransaction(
            user_id=user.id,
            provider="stripe",
            currency="KES",
            amount_cents=5000,
            status="succeeded",
            paid_cents=5000,
            provider_metadata={"status": "succeeded"},
            idempotency_key="same-key",
        )
        db.session.add(payment)
        db.session.commit()

        duplicate = PaymentTransaction(
            user_id=user.id,
            provider="stripe",
            currency="KES",
            amount_cents=5000,
            status="succeeded",
            paid_cents=5000,
            provider_metadata={"status": "succeeded"},
            idempotency_key="same-key",
        )
        db.session.add(duplicate)
        try:
            db.session.commit()
        except Exception:
            db.session.rollback()
            assert True
        else:
            assert False, "Expected duplicate idempotency key to be rejected."


models.py
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import CheckConstraint
from sqlalchemy.orm import validates

from extensions import db


class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    full_name = db.Column(db.String(255), nullable=True)
    country_code = db.Column(db.String(10), nullable=True)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    wallet = db.relationship("Wallet", back_populates="user", uselist=False, cascade="save-update")
    transactions = db.relationship("PaymentTransaction", back_populates="user", cascade="save-update")
    ledger_entries = db.relationship("CreditLedgerEntry", back_populates="user", cascade="save-update")

    def __repr__(self):
        return f"<User {self.email}>"


class Wallet(db.Model):
    __tablename__ = "wallets"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"), unique=True, nullable=True)
    currency = db.Column(db.String(8), nullable=False, default="USD")
    balance_credits = db.Column(db.Integer, nullable=False, default=0)
    status = db.Column(db.String(32), nullable=False, default="active")
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    __table_args__ = (
        CheckConstraint("balance_credits >= 0", name="wallet_balance_non_negative"),
    )

    user = db.relationship("User", back_populates="wallet")
    ledger_entries = db.relationship("CreditLedgerEntry", back_populates="wallet", cascade="save-update")

    @validates("balance_credits")
    def validate_balance(self, key, value):
        if value < 0:
            raise ValueError("Wallet balance cannot be negative.")
        return value

    def add_credits(self, amount_credits: int, reason: str, *, user=None, payment_transaction=None):
        if amount_credits <= 0:
            raise ValueError("Credit amount must be positive.")
        self.balance_credits += amount_credits
        db.session.add(
            CreditLedgerEntry(
                wallet=self,
                user=user or self.user,
                payment_transaction=payment_transaction,
                entry_type="grant",
                amount_credits=amount_credits,
                currency=self.currency,
                reason=reason,
                extra_data={"wallet_balance_after": self.balance_credits},
            )
        )
        return self

    def spend_credits(self, amount_credits: int, reason: str, *, user=None, payment_transaction=None):
        if amount_credits <= 0:
            raise ValueError("Debit amount must be positive.")
        if self.balance_credits < amount_credits:
            raise ValueError("Insufficient wallet credits.")
        self.balance_credits -= amount_credits
        db.session.add(
            CreditLedgerEntry(
                wallet=self,
                user=user or self.user,
                payment_transaction=payment_transaction,
                entry_type="debit",
                amount_credits=-amount_credits,
                currency=self.currency,
                reason=reason,
                extra_data={"wallet_balance_after": self.balance_credits},
            )
        )
        return self

    def __repr__(self):
        return f"<Wallet {self.user_id} {self.balance_credits} {self.currency}>"


class CreditPackage(db.Model):
    __tablename__ = "credit_packages"

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(64), unique=True, nullable=False, index=True)
    name = db.Column(db.String(128), nullable=False)
    description = db.Column(db.Text, nullable=True)
    currency = db.Column(db.String(8), nullable=False)
    price_cents = db.Column(db.Integer, nullable=False)
    credit_units = db.Column(db.Integer, nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    sort_order = db.Column(db.Integer, default=0, nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    __table_args__ = (
        CheckConstraint("price_cents >= 0", name="credit_package_price_non_negative"),
        CheckConstraint("credit_units > 0", name="credit_package_credit_units_positive"),
    )

    def __repr__(self):
        return f"<CreditPackage {self.code}>"


class PaymentTransaction(db.Model):
    __tablename__ = "payment_transactions"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    provider = db.Column(db.String(64), nullable=False, default="stripe")
    provider_payment_id = db.Column(db.String(255), nullable=True, index=True)
    provider_session_id = db.Column(db.String(255), nullable=True, index=True)
    currency = db.Column(db.String(8), nullable=False)
    amount_cents = db.Column(db.Integer, nullable=False)
    status = db.Column(db.String(32), nullable=False, default="pending")
    paid_cents = db.Column(db.Integer, nullable=False, default=0)
    provider_metadata = db.Column(db.JSON, nullable=True, default=dict)
    idempotency_key = db.Column(db.String(255), nullable=True, unique=True, index=True)
    webhook_event_id = db.Column(db.String(255), nullable=True, unique=True, index=True)
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    __table_args__ = (
        CheckConstraint("amount_cents >= 0", name="payment_transaction_amount_non_negative"),
        CheckConstraint("paid_cents >= 0", name="payment_transaction_paid_non_negative"),
    )

    user = db.relationship("User", back_populates="transactions")
    ledger_entries = db.relationship("CreditLedgerEntry", back_populates="payment_transaction", cascade="save-update")

    def __repr__(self):
        return f"<PaymentTransaction {self.provider_payment_id or self.id} {self.status}>"


class CreditLedgerEntry(db.Model):
    __tablename__ = "credit_ledger_entries"

    id = db.Column(db.Integer, primary_key=True)
    wallet_id = db.Column(db.Integer, db.ForeignKey("wallets.id", ondelete="SET NULL"), nullable=True, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    payment_transaction_id = db.Column(db.Integer, db.ForeignKey("payment_transactions.id", ondelete="SET NULL"), nullable=True)
    entry_type = db.Column(db.String(32), nullable=False)
    amount_credits = db.Column(db.Integer, nullable=False)
    currency = db.Column(db.String(8), nullable=False)
    reason = db.Column(db.String(255), nullable=False)
    extra_data = db.Column(db.JSON, nullable=True, default=dict)
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    __table_args__ = (
        CheckConstraint("amount_credits != 0", name="credit_ledger_entry_amount_non_zero"),
    )

    wallet = db.relationship("Wallet", back_populates="ledger_entries")
    user = db.relationship("User", back_populates="ledger_entries")
    payment_transaction = db.relationship("PaymentTransaction", back_populates="ledger_entries")

    def __repr__(self):
        return f"<CreditLedgerEntry {self.entry_type} {self.amount_credits}>"


def get_or_create_wallet(user_id: int, currency: str = "USD") -> Wallet:
    wallet = Wallet.query.filter_by(user_id=user_id).first()
    if wallet is None:
        wallet = Wallet(user_id=user_id, currency=currency, balance_credits=0)
        db.session.add(wallet)
        db.session.commit()
    return wallet


__all__ = [
    "User",
    "Wallet",
    "CreditPackage",
    "PaymentTransaction",
    "CreditLedgerEntry",
    "get_or_create_wallet",
]


migrations/env.py
from __future__ import annotations

import logging
from logging.config import fileConfig

from alembic import context
from flask import current_app

from extensions import db

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = db.metadata


def run_migrations_offline() -> None:
    url = current_app.config.get("SQLALCHEMY_DATABASE_URI")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = db.engine
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()


migrations/versions/20261022_initial_billing_schema.py
"""Initial billing models and ledger tables.

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
        sa.Column("is_active", sa.Boolean(), nullable=False),
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
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
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


def downgrade() -> None:
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


pytest.ini
[pytest]
testpaths = tests


tests/conftest.py
import pytest

from app import create_app


@pytest.fixture()
def app():
    app = create_app(test_config={"TESTING": True, "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:"})
    app.config["SERVER_NAME"] = "localhost"
    with app.app_context():
        from extensions import db
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture()
def client(app):
    return app.test_client()


tests/test_billing_foundation.py
from extensions import db
from models import CreditLedgerEntry, PaymentTransaction, User, get_or_create_wallet


def test_app_initializes_with_test_database(app):
    assert app is not None
    assert app.config["TESTING"] is True
    assert "users" in db.metadata.tables
    assert "wallets" in db.metadata.tables
    assert "payment_transactions" in db.metadata.tables
    assert "credit_ledger_entries" in db.metadata.tables


def test_wallet_balance_and_ledger_integrity(app):
    with app.app_context():
        user = User(email="wallet@example.com", full_name="Wallet User")
        db.session.add(user)
        db.session.commit()

        wallet = get_or_create_wallet(user.id, currency="KES")
        wallet.add_credits(100, "initial credit", user=user)
        db.session.commit()
        assert wallet.balance_credits == 100

        wallet.spend_credits(40, "document generation", user=user)
        db.session.commit()
        assert wallet.balance_credits == 60

        ledger = CreditLedgerEntry.query.filter_by(user_id=user.id).all()
        assert len(ledger) == 2
        assert sum(entry.amount_credits for entry in ledger) == 60


def test_duplicate_payment_transaction_idempotency_is_protected(app):
    with app.app_context():
        user = User(email="pay@example.com", full_name="Pay User")
        db.session.add(user)
        db.session.commit()

        payment = PaymentTransaction(
            user_id=user.id,
            provider="stripe",
            currency="KES",
            amount_cents=5000,
            status="succeeded",
            paid_cents=5000,
            provider_metadata={"status": "succeeded"},
            idempotency_key="same-key",
        )
        db.session.add(payment)
        db.session.commit()

        duplicate = PaymentTransaction(
            user_id=user.id,
            provider="stripe",
            currency="KES",
            amount_cents=5000,
            status="succeeded",
            paid_cents=5000,
            provider_metadata={"status": "succeeded"},
            idempotency_key="same-key",
        )
        db.session.add(duplicate)
        try:
            db.session.commit()
        except Exception:
            db.session.rollback()
            assert True
        else:
            assert False, "Expected duplicate idempotency key to be rejected."


