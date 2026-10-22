from sqlalchemy.exc import IntegrityError

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
        assert sum(item.amount_credits for item in ledger) == 60


def test_duplicate_payment_idempotency_is_rejected(app):
    with app.app_context():
        user = User(email="pay@example.com", full_name="Pay User")
        db.session.add(user)
        db.session.commit()

        first = PaymentTransaction(
            user_id=user.id,
            provider="stripe",
            currency="KES",
            amount_cents=5000,
            status="succeeded",
            paid_cents=5000,
            provider_metadata={"status": "succeeded"},
            idempotency_key="same-key",
        )
        db.session.add(first)
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
        except IntegrityError:
            db.session.rollback()
            assert True
        else:
            db.session.rollback()
            assert False, "Expected duplicate idempotency key to be rejected."
