from __future__ import annotations

import hashlib
import json
import uuid
from typing import Optional

from flask import Blueprint, current_app, jsonify, request
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from extensions import db
from models import (
    CreditLedgerEntry,
    CreditPackage,
    PaymentTransaction,
    ensure_user,
    get_or_create_wallet,
    seed_default_credit_packages,
)
from payment_provider import PaymentProviderError, get_provider_adapter

billing_bp = Blueprint("billing_bp", __name__, url_prefix="/api")


def _serialize_package(pkg: CreditPackage) -> dict:
    return {
        "id": pkg.id,
        "code": pkg.code,
        "name": pkg.name,
        "description": pkg.description,
        "currency": pkg.currency,
        "price_cents": pkg.price_cents,
        "credit_units": pkg.credit_units,
    }


def _json_error(message: str, status: int):
    return jsonify({"success": False, "error": message}), status


def _provider():
    return get_provider_adapter(testing=bool(current_app.testing))


def _package_for_transaction(tx: PaymentTransaction, package_code: Optional[str] = None):
    metadata = tx.provider_metadata if isinstance(tx.provider_metadata, dict) else {}
    code = package_code or metadata.get("package_code")
    if not code:
        return None
    return CreditPackage.query.filter_by(code=code, is_active=True).first()


def _apply_credit_grant(tx: PaymentTransaction, *, package_code: Optional[str] = None):
    """Grant only for a known transaction verified as fully paid and correctly priced."""
    if tx.user_id is None or tx.status != "succeeded" or int(tx.paid_cents or 0) != int(tx.amount_cents or 0):
        return None

    package = _package_for_transaction(tx, package_code)
    if package is None:
        current_app.logger.error("No active package matched paid transaction %s", tx.id)
        return None
    if int(package.price_cents) != int(tx.amount_cents):
        current_app.logger.error("Package amount mismatch for transaction %s", tx.id)
        return None
    if (package.currency or "").upper() != (tx.currency or "").upper():
        current_app.logger.error("Package currency mismatch for transaction %s", tx.id)
        return None

    existing = CreditLedgerEntry.query.filter_by(
        payment_transaction_id=tx.id, entry_type="grant"
    ).first()
    if existing:
        return get_or_create_wallet(tx.user_id, currency=tx.currency)

    wallet = get_or_create_wallet(tx.user_id, currency=tx.currency)
    wallet.add_credits(
        int(package.credit_units),
        f"Payment grant via {tx.provider}",
        user=tx.user,
        payment_transaction=tx,
    )
    db.session.commit()
    return wallet


def _sync_small_package_price():
    """Apply the Small Pack price change to the existing database record only."""
    package = CreditPackage.query.filter_by(code="starter").first()
    if package is None:
        return
    changed = False
    if package.name != "Small Pack":
        package.name = "Small Pack"
        changed = True
    if package.price_cents != 1000:
        package.price_cents = 1000
        changed = True
    if package.currency != "KES":
        package.currency = "KES"
        changed = True
    if package.description != "25 credits":
        package.description = "25 credits"
        changed = True
    if changed:
        db.session.commit()


@billing_bp.get("/payments/packages")
def list_packages():
    _sync_small_package_price()
    packages = CreditPackage.query.filter_by(is_active=True).order_by(CreditPackage.sort_order).all()
    if not packages:
        packages = seed_default_credit_packages()
    return jsonify({
        "success": True,
        "provider": current_app.config.get("PAYMENT_PROVIDER", "paystack"),
        "packages": [_serialize_package(item) for item in packages],
    })


@billing_bp.post("/payments/checkout")
def checkout():
    if not current_app.config.get("BILLING_ENABLED", False):
        return _json_error("Paid checkout is currently disabled.", 503)

    body = request.get_json(silent=True) or {}
    email = (body.get("email") or body.get("user_email") or "").strip().lower()
    package_code = (body.get("package_code") or "").strip()
    if not email or len(email) > 254 or "@" not in email or email.startswith("@") or email.endswith("@"):
        return _json_error("A valid email address is required.", 400)
    if not package_code:
        return _json_error("package_code is required.", 400)

    _sync_small_package_price()
    package = CreditPackage.query.filter_by(code=package_code, is_active=True).first()
    if package is None:
        packages = seed_default_credit_packages()
        package = next((p for p in packages if p.code == package_code and p.is_active), None)
    if package is None:
        return _json_error("The selected credit package is unavailable.", 404)

    # Reuse a caller-provided idempotency key where supplied; otherwise generate one.
    supplied_key = (body.get("idempotency_key") or "").strip()
    if len(supplied_key) > 180:
        return _json_error("idempotency_key is too long.", 400)
    reference = supplied_key or f"dc_{uuid.uuid4().hex}"

    existing = PaymentTransaction.query.filter_by(idempotency_key=reference).first()
    if existing:
        if existing.user and existing.user.email.lower() != email:
            return _json_error("That checkout reference belongs to another account.", 409)
        existing_metadata = existing.provider_metadata if isinstance(existing.provider_metadata, dict) else {}
        existing_checkout_url = existing_metadata.get("checkout_url")
        if existing.status == "failed":
            return _json_error("The previous checkout could not be initialized. Start a new checkout.", 409)
        if existing_checkout_url and existing.status in {"pending", "succeeded"}:
            return jsonify({
                "success": True,
                "checkout": {
                    "reference": existing.idempotency_key,
                    "provider_reference": existing.provider_payment_id,
                    "url": existing_checkout_url,
                    "status": existing.status,
                    "currency": existing.currency,
                    "amount_cents": existing.amount_cents,
                },
            })
        return _json_error("A checkout with this reference is already being processed. Please retry with a new checkout reference.", 409)

    user = ensure_user(email, full_name=body.get("full_name"), country_code=body.get("country_code") or "KE")
    currency = (package.currency or "KES").upper()
    amount_cents = int(package.price_cents)
    if amount_cents <= 0 or int(package.credit_units) <= 0:
        return _json_error("This package is not configured correctly.", 500)

    provider = _provider()
    tx = PaymentTransaction(
        user_id=user.id,
        provider=provider.provider_name,
        currency=currency,
        amount_cents=amount_cents,
        status="pending",
        paid_cents=0,
        idempotency_key=reference,
        provider_payment_id=reference,
        provider_metadata={"package_code": package.code},
    )
    db.session.add(tx)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        raced = PaymentTransaction.query.filter_by(idempotency_key=reference).first()
        if raced:
            return _json_error("A checkout with this reference already exists. Retry using its reference.", 409)
        return _json_error("Could not create checkout. Please retry.", 409)

    try:
        session = provider.create_checkout_session(
            amount_cents=amount_cents,
            currency=currency,
            customer_email=email,
            metadata={"user_id": str(user.id), "transaction_id": str(tx.id)},
            package_code=package.code,
            reference=reference,
        )
    except PaymentProviderError as exc:
        tx.status = "failed"
        db.session.commit()
        current_app.logger.warning("Checkout initialization failed: %s", exc)
        return _json_error("Payment checkout is temporarily unavailable. Please try again later.", 503)

    provider_ref = str(session.get("reference") or session.get("id") or reference)
    tx.provider_payment_id = provider_ref
    tx.provider_session_id = str(session.get("id") or provider_ref)
    metadata = tx.provider_metadata if isinstance(tx.provider_metadata, dict) else {}
    metadata.update(session.get("metadata") or {})
    metadata["package_code"] = package.code
    metadata["checkout_url"] = session.get("url")
    tx.provider_metadata = metadata
    db.session.commit()

    return jsonify({
        "success": True,
        "checkout": {
            "reference": tx.idempotency_key,
            "provider_reference": provider_ref,
            "url": session.get("url"),
            "status": tx.status,
            "provider": tx.provider,
            "currency": tx.currency,
            "amount_cents": tx.amount_cents,
            "credit_units": package.credit_units,
        },
    })


def _find_transaction(reference: str):
    if not reference:
        return None
    tx = PaymentTransaction.query.filter_by(provider_payment_id=reference).first()
    if tx is None:
        tx = PaymentTransaction.query.filter_by(provider_session_id=reference).first()
    if tx is None:
        tx = PaymentTransaction.query.filter_by(idempotency_key=reference).first()
    return tx


def _finalize_verified_payment(tx: PaymentTransaction, verified: dict):
    provider_name = str(verified.get("provider") or "").lower()
    if provider_name and provider_name != str(tx.provider).lower():
        return _json_error("Payment provider mismatch.", 400)
    returned_reference = str(verified.get("reference") or "")
    if not returned_reference or returned_reference not in {
        str(tx.provider_payment_id or ""), str(tx.provider_session_id or ""), str(tx.idempotency_key or "")
    }:
        return _json_error("Payment reference mismatch.", 400)
    amount = int(verified.get("amount_cents") or 0)
    currency = str(verified.get("currency") or "").upper()
    if amount != int(tx.amount_cents) or currency != str(tx.currency).upper():
        return _json_error("The verified payment amount or currency does not match this checkout.", 400)
    if verified.get("status") != "succeeded":
        return _json_error("Payment has not been confirmed as successful.", 402)

    tx.status = "succeeded"
    tx.paid_cents = amount
    try:
        db.session.commit()
        wallet = _apply_credit_grant(tx)
    except SQLAlchemyError:
        db.session.rollback()
        current_app.logger.exception("Could not finalize verified payment transaction %s", tx.id)
        return _json_error("Payment was verified, but account crediting needs a retry.", 500)
    return jsonify({
        "success": True,
        "status": "succeeded",
        "reference": tx.idempotency_key,
        "credits_balance": wallet.balance_credits if wallet is not None else None,
    })


@billing_bp.post("/payments/verify")
def verify_payment():
    body = request.get_json(silent=True) or {}
    reference = str(body.get("reference") or body.get("session_id") or "").strip()
    if not reference:
        return _json_error("Payment reference is required.", 400)
    tx = _find_transaction(reference)
    if tx is None:
        return _json_error("Unknown payment reference.", 404)
    if tx.status == "succeeded" and int(tx.paid_cents or 0) == int(tx.amount_cents or 0):
        try:
            wallet = _apply_credit_grant(tx)
        except SQLAlchemyError:
            db.session.rollback()
            return _json_error("Could not confirm account credits. Please retry.", 500)
        return jsonify({
            "success": True, "status": "succeeded", "reference": tx.idempotency_key,
            "credits_balance": wallet.balance_credits if wallet is not None else None,
        })

    try:
        provider = _provider()
        # Stripe verifies by Checkout Session ID, while the public checkout
        # reference may be our own idempotency key. Use the stored provider ID.
        provider_reference = tx.provider_session_id or tx.provider_payment_id or reference
        verified = provider.verify_payment(
            payment_reference=provider_reference,
            amount_cents=int(tx.amount_cents),
            currency=tx.currency,
            metadata=tx.provider_metadata if isinstance(tx.provider_metadata, dict) else {},
        )
    except PaymentProviderError as exc:
        current_app.logger.warning("Payment verification failed: %s", exc)
        return _json_error("Unable to verify this payment right now.", 503)
    return _finalize_verified_payment(tx, verified)


@billing_bp.post("/payments/webhook")
def payment_webhook():
    raw_body = request.get_data(cache=False)
    provider_name = (current_app.config.get("PAYMENT_PROVIDER") or "paystack").lower()
    signature = request.headers.get("x-paystack-signature") if provider_name == "paystack" else request.headers.get("Stripe-Signature")
    try:
        event = _provider().verify_webhook(
            raw_body=raw_body,
            signature=signature,
            headers=dict(request.headers),
        )
    except (ValueError, PaymentProviderError) as exc:
        current_app.logger.warning("Rejected payment webhook: %s", exc)
        return _json_error("Invalid webhook signature or payload.", 400)

    event_type = str(event.get("event") or event.get("type") or "")
    data = event.get("data") or {}
    if provider_name == "paystack":
        if event_type != "charge.success":
            return jsonify({"success": True, "ignored": True})
        reference = str(data.get("reference") or "")
        amount = int(data.get("amount") or 0)
        currency = str(data.get("currency") or "").upper()
        event_id = str(data.get("id") or "") or hashlib.sha256(raw_body).hexdigest()
        paid = data.get("status") == "success"
    else:
        if event_type != "checkout.session.completed":
            return jsonify({"success": True, "ignored": True})
        reference = str(data.get("id") or "")
        amount = int(data.get("amount_total") or 0)
        currency = str(data.get("currency") or "").upper()
        event_id = str(event.get("id") or "") or hashlib.sha256(raw_body).hexdigest()
        paid = data.get("payment_status") == "paid"

    tx = _find_transaction(reference)
    if tx is None:
        current_app.logger.warning("Ignoring webhook for unknown payment reference %s", reference)
        return jsonify({"success": True, "ignored": True})

    # Duplicate successful notifications are safe and do not issue a second grant.
    if tx.status == "succeeded" and int(tx.paid_cents or 0) == int(tx.amount_cents or 0):
        try:
            _apply_credit_grant(tx)
        except SQLAlchemyError:
            db.session.rollback()
            return _json_error("Could not reconcile payment credits.", 500)
        return jsonify({"success": True, "duplicate": True})

    if not paid or amount != int(tx.amount_cents) or currency != str(tx.currency).upper():
        current_app.logger.warning("Webhook amount/status mismatch for transaction %s", tx.id)
        return _json_error("Payment notification did not match the pending checkout.", 400)

    # Never trust package/user values supplied by the webhook; transaction values are authoritative.
    tx.status = "succeeded"
    tx.paid_cents = amount
    # Store the provider event ID in the dedicated unique column when available.
    # This helps prevent one event being accepted against multiple transactions.
    if hasattr(tx, "webhook_event_id"):
        tx.webhook_event_id = event_id
    try:
        db.session.commit()
        wallet = _apply_credit_grant(tx)
    except SQLAlchemyError:
        db.session.rollback()
        current_app.logger.exception("Webhook credit grant failed for transaction %s", tx.id)
        return _json_error("Payment received; credit reconciliation will need a retry.", 500)
    return jsonify({"success": True, "credited": wallet is not None})
