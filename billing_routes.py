from __future__ import annotations

import hashlib
import json
from typing import Optional

from flask import Blueprint, current_app, jsonify, request
from sqlalchemy.exc import SQLAlchemyError

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


def _package_for_transaction(tx: PaymentTransaction, package_code: Optional[str] = None):
    metadata = tx.provider_metadata if isinstance(tx.provider_metadata, dict) else {}
    code = package_code or metadata.get("package_code")
    if not code:
        return None
    return CreditPackage.query.filter_by(code=code, is_active=True).first()


def _apply_credit_grant(tx: PaymentTransaction, *, package_code: Optional[str] = None):
    """Grant credits once, and only for a known, paid, correctly priced transaction."""
    if tx.user_id is None or tx.status != "succeeded" or tx.paid_cents != tx.amount_cents:
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
        package.credit_units,
        f"Payment grant via {tx.provider}",
        user=tx.user,
        payment_transaction=tx,
    )
    db.session.commit()
    return wallet


@billing_bp.get("/payments/packages")
def list_packages():
    packages = CreditPackage.query.filter_by(is_active=True).order_by(CreditPackage.sort_order).all()
    if not packages:
        packages = seed_default_credit_packages()
    return jsonify({
        "provider": current_app.config.get("PAYMENT_PROVIDER", "paystack"),
        "packages": [_serialize_package(item) for item in packages],
    })


@billing_bp.post("/payments/checkout")
def checkout():
    body = request.get_json(silent=True) or {}
    email = (body.get("email") or body.get("user_email") or "").strip().lower()
    if not email or "@" not in email:
