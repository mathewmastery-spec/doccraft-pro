import os
import json
from datetime import datetime, timezone

from flask import current_app
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

    wallet = db.relationship("Wallet", back_populates="user", uselist=False, cascade="all, delete-orphan")
    transactions = db.relationship("PaymentTransaction", back_populates="user", cascade="all, delete-orphan")
    ledger_entries = db.relationship("CreditLedgerEntry", back_populates="user", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<User {self.email}>"


class Wallet(db.Model):
    __tablename__ = "wallets"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    currency = db.Column(db.String(8), nullable=False, default="USD")
    balance_cents = db.Column(db.Integer, nullable=False, default=0)
    status = db.Column(db.String(32), nullable=False, default="active")
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    user = db.relationship("User", back_populates="wallet")
    ledger_entries = db.relationship("CreditLedgerEntry", back_populates="wallet", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Wallet {self.user_id} {self.balance_cents} {self.currency}>"


class CreditPackage(db.Model):
    __tablename__ = "credit_packages"

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(64), unique=True, nullable=False, index=True)
    name = db.Column(db.String(128), nullable=False)
    description = db.Column(db.Text, nullable=True)
    currency = db.Column(db.String(8), nullable=False)
    price_cents = db.Column(db.Integer, nullable=False)
    credit_amount = db.Column(db.Integer, nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    sort_order = db.Column(db.Integer, default=0, nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

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
    amount_paid_cents = db.Column(db.Integer, nullable=False, default=0)
    metadata = db.Column(db.JSON, nullable=True, default=dict)
    idempotency_key = db.Column(db.String(255), nullable=True, unique=True, index=True)
    webhook_event_id = db.Column(db.String(255), nullable=True, unique=True, index=True)
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    user = db.relationship("User", back_populates="transactions")
    ledger_entries = db.relationship("CreditLedgerEntry", back_populates="payment_transaction", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<PaymentTransaction {self.provider_payment_id or self.id} {self.status}>"


class CreditLedgerEntry(db.Model):
    __tablename__ = "credit_ledger_entries"

    id = db.Column(db.Integer, primary_key=True)
    wallet_id = db.Column(db.Integer, db.ForeignKey("wallets.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    payment_transaction_id = db.Column(db.Integer, db.ForeignKey("payment_transactions.id", ondelete="SET NULL"), nullable=True)
    entry_type = db.Column(db.String(32), nullable=False)  # grant, refund, debit, adjustment
    amount_cents = db.Column(db.Integer, nullable=False)
    currency = db.Column(db.String(8), nullable=False)
    reason = db.Column(db.String(255), nullable=False)
    metadata = db.Column(db.JSON, nullable=True, default=dict)
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    wallet = db.relationship("Wallet", back_populates="ledger_entries")
    user = db.relationship("User", back_populates="ledger_entries")
    payment_transaction = db.relationship("PaymentTransaction", back_populates="ledger_entries")

    def __repr__(self):
        return f"<CreditLedgerEntry {self.entry_type} {self.amount_cents}>"


def ensure_wallet_for_user(user_id: int, currency: str = "USD") -> Wallet:
    wallet = Wallet.query.filter_by(user_id=user_id).first()
    if wallet is None:
        wallet = Wallet(user_id=user_id, currency=currency, balance_cents=0)
        db.session.add(wallet)
        db.session.commit()
    return wallet
