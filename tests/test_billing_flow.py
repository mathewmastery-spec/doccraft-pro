from __future__ import annotations

import json

from extensions import db
from models import CreditLedgerEntry, GenerationRequest, PaymentTransaction, User, ensure_user, get_or_create_wallet


def test_checkout_and_payment_verification(app):
    with app.app_context():
        client = app.test_client()
        res = client.post("/api/payments/checkout", json={"email": "kenya@example.com", "full_name": "Kenya User", "package_code": "starter"})
        assert res.status_code == 200
        body = res.get_json()
        assert body["success"] is True
        tx = PaymentTransaction.query.filter_by(idempotency_key=body["checkout"]["reference"]).first()
        assert tx is not None
        verify = client.post("/api/payments/verify", json={"reference": tx.provider_payment_id})
        assert verify.status_code == 200
        wallet = get_or_create_wallet(tx.user_id, currency="KES")
        assert wallet.balance_credits >= 25


def test_duplicate_webhook_is_ignored(app):
    with app.app_context():
        user = ensure_user("dup@example.com", full_name="Dup")
        tx = PaymentTransaction(user_id=user.id, provider="paystack", currency="KES", amount_cents=50000, status="pending", paid_cents=0, idempotency_key="dup-ref", provider_payment_id="dup-ref", provider_metadata={"package_code": "starter"})
        db.session.add(tx)
        db.session.commit()
        event = {"event": "charge.success", "data": {"reference": "dup-ref", "amount": 50000, "metadata": {"package_code": "starter"}}}
        client = app.test_client()
        first = client.post("/api/payments/webhook", data=json.dumps(event), content_type="application/json")
        second = client.post("/api/payments/webhook", data=json.dumps(event), content_type="application/json")
        assert first.status_code == 200
        assert second.status_code == 200
        tx_after = PaymentTransaction.query.filter_by(idempotency_key="dup-ref").first()
        assert tx_after.status == "succeeded"


def test_generate_deducts_wallet_credit_once(app):
    with app.app_context():
        user = ensure_user("billing@example.com", full_name="Billing User")
        wallet = get_or_create_wallet(user.id, currency="KES")
        wallet.add_credits(10, "top up", user=user)
        db.session.commit()
        client = app.test_client()
        res = client.post("/api/generate", json={"doc_type": "resume", "user_input": "Alice Example", "email": "billing@example.com", "full_name": "Billing User", "idempotency_key": "gen-1"})
        assert res.status_code == 200
        wallet = get_or_create_wallet(user.id, currency="KES")
        assert wallet.balance_credits <= 9
        duplicate = client.post("/api/generate", json={"doc_type": "resume", "user_input": "Alice Example", "email": "billing@example.com", "full_name": "Billing User", "idempotency_key": "gen-1"})
        assert duplicate.status_code == 200
