from __future__ import annotations

import json

from extensions import db
from models import (
    CreditLedgerEntry,
    CreditPackage,
    PaymentTransaction,
    User,
    Wallet,
)


def test_packages_endpoint_returns_configured_packages(client):
    response = client.get("/api/payments/packages")

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["success"] is True
    codes = {item["code"] for item in payload["packages"]}
    assert {"starter", "growth", "pro"}.issubset(codes)


def test_checkout_requires_email_and_package(client):
    response = client.post("/api/payments/checkout", json={"package_code": "starter"})

    assert response.status_code == 400
    assert response.get_json()["success"] is False


def test_checkout_rejects_unknown_package(client):
    response = client.post(
        "/api/payments/checkout",
        json={"email": "customer@example.com", "package_code": "not-a-real-package"},
    )

    assert response.status_code == 404
    assert response.get_json()["success"] is False


def test_checkout_uses_server_price_and_returns_checkout_reference(client):
    response = client.post(
        "/api/payments/checkout",
        json={
            "email": "customer@example.com",
            "package_code": "starter",
            "amount_cents": 1,
            "credit_units": 999999,
        },
    )

    assert response.status_code == 200
    payload = response.get_json()
    checkout = payload["checkout"]
    package = CreditPackage.query.filter_by(code="starter").one()
    transaction = PaymentTransaction.query.filter_by(
        idempotency_key=checkout["reference"]
    ).one()

    assert checkout["amount_cents"] == package.price_cents
    assert checkout["credit_units"] == package.credit_units
    assert transaction.amount_cents == package.price_cents
    assert transaction.status == "pending"
    assert transaction.user.email == "customer@example.com"


def test_checkout_idempotency_key_cannot_be_reused_for_another_email(client):
    first = client.post(
        "/api/payments/checkout",
        json={
            "email": "first@example.com",
            "package_code": "starter",
            "idempotency_key": "stable-test-reference",
        },
    )
    assert first.status_code == 200

    second = client.post(
        "/api/payments/checkout",
        json={
            "email": "second@example.com",
            "package_code": "starter",
            "idempotency_key": "stable-test-reference",
        },
    )
    assert second.status_code == 409


def test_generation_rejects_invalid_payload_before_calling_provider(client, monkeypatch):
    response = client.post("/api/generate", json={"doc_type": "not-supported"})

    assert response.status_code == 400
    assert response.get_json()["success"] is False


def test_wallet_model_rejects_negative_credit_balance(app):
    with app.app_context():
        from models import ensure_user, get_or_create_wallet

        user = ensure_user("wallet-test@example.com")
        wallet = get_or_create_wallet(user.id, currency="KES")

        try:
            wallet.balance_credits = -1
            assert False, "negative balance should be rejected"
        except ValueError:
            db.session.rollback()

        wallet = Wallet.query.filter_by(user_id=user.id).one()
        assert wallet.balance_credits == 0



def _create_starter_checkout(client, email="webhook-test@example.com"):
    response = client.post(
        "/api/payments/checkout",
        json={"email": email, "package_code": "starter"},
    )
    assert response.status_code == 200
    return response.get_json()["checkout"]


def test_successful_payment_webhook_grants_credits_only_once(client):
    checkout = _create_starter_checkout(client)
    transaction = PaymentTransaction.query.filter_by(
        idempotency_key=checkout["reference"]
    ).one()
    event = {
        "event": "charge.success",
        "data": {
            "id": 987654,
            "reference": checkout["provider_reference"],
            "amount": transaction.amount_cents,
            "currency": transaction.currency,
            "status": "success",
        },
    }

    first = client.post("/api/payments/webhook", json=event)
    assert first.status_code == 200
    assert first.get_json()["credited"] is True

    second = client.post("/api/payments/webhook", json=event)
    assert second.status_code == 200
    assert second.get_json()["duplicate"] is True

    wallet = Wallet.query.filter_by(user_id=transaction.user_id).one()
    grants = CreditLedgerEntry.query.filter_by(
        payment_transaction_id=transaction.id,
        entry_type="grant",
    ).all()
    assert wallet.balance_credits == 25
    assert len(grants) == 1


def test_payment_webhook_rejects_amount_mismatch(client):
    checkout = _create_starter_checkout(client, email="mismatch@example.com")
    transaction = PaymentTransaction.query.filter_by(
        idempotency_key=checkout["reference"]
    ).one()
    event = {
        "event": "charge.success",
        "data": {
            "id": 987655,
            "reference": checkout["provider_reference"],
            "amount": transaction.amount_cents - 1,
            "currency": transaction.currency,
            "status": "success",
        },
    }

    response = client.post("/api/payments/webhook", json=event)

    assert response.status_code == 400
    db_transaction = db.session.get(PaymentTransaction, transaction.id)
    assert db_transaction.status == "pending"
    assert db_transaction.paid_cents == 0
