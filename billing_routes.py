from __future__ import annotations

import hashlib
import json
import os
from typing import Any, Dict, Optional

from flask import Blueprint, current_app, jsonify, request

from extensions import db
from models import CreditLedgerEntry, CreditPackage, GenerationRequest, PaymentTransaction, User, Wallet, ensure_user, get_or_create_wallet, seed_default_credit_packages
from payment_provider import get_provider_adapter

billing_bp = Blueprint("billing_bp", __name__, url_prefix="/api")


def _serialize_package(pkg: CreditPackage):
    return {
        "id": pkg.id,
        "code": pkg.code,
        "name": pkg.name,
        "description": pkg.description,
        "currency": pkg.currency,
        "price_cents": pkg.price_cents,
        "credit_units": pkg.credit_units,
    }


def _apply_credit_grant(tx: PaymentTransaction, *, package_code: Optional[str] = None):
    if tx.user_id is None:
        return None
    package = None
    if package_code:
        package = CreditPackage.query.filter_by(code=package_code, is_active=True).first()
    if package is None:
        package = CreditPackage.query.filter_by(is_active=True).order_by(CreditPackage.sort_order).first()
    if package is None:
        return None
    wallet = get_or_create_wallet(tx.user_id, currency=tx.currency or package.currency)
    existing = CreditLedgerEntry.query.filter_by(payment_transaction_id=tx.id, entry_type="grant").first()
    if existing is None:
        wallet.add_credits(package.credit_units, f"Payment grant via {tx.provider}", user=tx.user, payment_transaction=tx)
        db.session.commit()
    return wallet


@billing_bp.get("/payments/packages")
def list_packages():
    packages = CreditPackage.query.filter_by(is_active=True).order_by(CreditPackage.sort_order).all()
    if not packages:
        packages = seed_default_credit_packages()
    return jsonify({"provider": current_app.config.get("PAYMENT_PROVIDER", "paystack"), "packages": [_serialize_package(item) for item in packages]})


@billing_bp.post("/payments/checkout")
def checkout():
    body = request.get_json(silent=True) or {}
    email = (body.get("email") or body.get("user_email") or "").strip().lower()
    if not email:
        return jsonify({"success": False, "error": "An email address is required to create the checkout."}), 400
    full_name = body.get("full_name")
    country_code = body.get("country_code") or "KE"
    user = ensure_user(email, full_name=full_name, country_code=country_code)
    package_code = body.get("package_code") or "starter"
    package = CreditPackage.query.filter_by(code=package_code, is_active=True).first()
    if package is None:
        seed_default_credit_packages()
        package = CreditPackage.query.filter_by(code=package_code, is_active=True).first()
    if package is None:
        return jsonify({"success": False, "error": "Unknown credit package selected."}), 404

    provider = get_provider_adapter()
    session = provider.create_checkout_session(
        amount_cents=int(package.price_cents),
        currency=package.currency,
        customer_email=email,
        metadata={"package_code": package.code, "user_email": email},
        package_code=package.code,
    )
    reference = session.get("reference") or session.get("id") or os.urandom(8).hex()
    tx = PaymentTransaction.query.filter_by(idempotency_key=reference).first()
    if tx is None:
        tx = PaymentTransaction(
            user_id=user.id,
            provider=provider.provider_name,
            provider_payment_id=reference,
            provider_session_id=session.get("id"),
            currency=package.currency,
            amount_cents=int(package.price_cents),
            status="pending",
            paid_cents=0,
            provider_metadata={"package_code": package.code, **(session.get("metadata") or {})},
            idempotency_key=reference,
        )
        db.session.add(tx)
        db.session.commit()
    return jsonify({
        "success": True,
        "provider": provider.provider_name,
        "checkout": {
            "id": tx.id,
            "session_id": tx.provider_session_id,
            "reference": tx.provider_payment_id,
            "status": tx.status,
            "url": session.get("url"),
        },
        "transaction": {"id": tx.id, "status": tx.status, "currency": tx.currency, "amount_cents": tx.amount_cents},
    })


@billing_bp.post("/payments/verify")
def verify_payment():
    body = request.get_json(silent=True) or {}
    reference = body.get("reference") or body.get("payment_reference")
    if not reference:
        return jsonify({"success": False, "error": "A payment reference is required."}), 400
    tx = PaymentTransaction.query.filter_by(provider_payment_id=reference).first() or PaymentTransaction.query.filter_by(idempotency_key=reference).first()
    if tx is None:
        return jsonify({"success": False, "error": "Unknown payment reference."}), 404
    provider = get_provider_adapter()
    result = provider.verify_payment(payment_reference=reference, amount_cents=tx.amount_cents, currency=tx.currency)
    if result.get("status") not in {"succeeded", "success"}:
        tx.status = "failed"
        tx.provider_metadata = {**(tx.provider_metadata or {}), "verification": result}
        db.session.commit()
        return jsonify({"success": False, "error": "Payment verification failed.", "status": tx.status}), 402
    tx.status = "succeeded"
    tx.paid_cents = int(result.get("amount_cents") or tx.amount_cents)
    tx.provider_metadata = {**(tx.provider_metadata or {}), "verification": result}
    db.session.commit()
    package_code = (tx.provider_metadata or {}).get("package_code") or "starter"
    grant = _apply_credit_grant(tx, package_code=package_code)
    return jsonify({"success": True, "message": "Payment verified and wallet credited.", "payment": {"id": tx.id, "status": tx.status}, "wallet_balance": grant.balance_credits if grant else 0})


@billing_bp.post("/payments/webhook")
def payment_webhook():
    raw = request.get_data(cache=False)
    headers = dict(request.headers)
    signature = headers.get("X-Signature") or headers.get("Stripe-Signature") or headers.get("x-paystack-signature")
    provider = get_provider_adapter()
    try:
        event = provider.verify_webhook(raw_body=raw, signature=signature, headers=headers)
    except ValueError:
        return jsonify({"success": False, "error": "Invalid webhook signature."}), 401

    event_type = event.get("event") or event.get("type") or "unknown"
    if provider.provider_name == "paystack":
        reference = (event.get("data") or {}).get("reference") or (event.get("eventData") or {}).get("reference")
    else:
        reference = (event.get("data") or {}).get("object", {}).get("id")
    if not reference:
        return jsonify({"success": True, "message": "Webhook ignored: missing reference."})

    tx = PaymentTransaction.query.filter_by(idempotency_key=reference).first() or PaymentTransaction.query.filter_by(provider_payment_id=reference).first()
    if tx is None:
        tx = PaymentTransaction(
            user_id=None,
            provider=provider.provider_name,
            provider_payment_id=reference,
            currency="KES",
            amount_cents=0,
            status="pending",
            paid_cents=0,
            provider_metadata=event,
            idempotency_key=reference,
            webhook_event_id=f"{event_type}:{reference}",
        )
        db.session.add(tx)
        db.session.commit()

    if tx.status == "succeeded" and tx.webhook_event_id == f"{event_type}:{reference}":
        return jsonify({"success": True, "message": "Duplicate webhook ignored."})

    tx.webhook_event_id = f"{event_type}:{reference}"
    tx.provider_metadata = {**(tx.provider_metadata or {}), "event": event}
    if event_type in {"charge.success", "payment.success", "checkout.session.completed", "invoice.paid"}:
        tx.status = "succeeded"
        tx.paid_cents = int((event.get("data") or {}).get("amount", tx.amount_cents) or tx.amount_cents)
        tx.provider_payment_id = reference
        db.session.commit()
        _apply_credit_grant(tx, package_code=(event.get("data") or {}).get("metadata", {}).get("package_code") or "starter")
        return jsonify({"success": True, "message": "Webhook processed; wallet credited once."})

    tx.status = "failed"
    db.session.commit()
    return jsonify({"success": True, "message": "Webhook processed with failed payment state."})


@billing_bp.get("/payments/health")
def payment_health():
    return jsonify({"success": True, "provider": get_provider_adapter().provider_name, "mode": os.getenv("PAYMENT_PROVIDER_MODE", "sandbox")})
