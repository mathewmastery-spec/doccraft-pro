from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import CheckConstraint, UniqueConstraint
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
    generation_requests = db.relationship("GenerationRequest", back_populates="user", cascade="save-update")

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

    __table_args__ = (CheckConstraint("balance_credits >= 0", name="wallet_balance_non_negative"),)

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
    provider = db.Column(db.String(64), nullable=False, default="paystack")
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
        UniqueConstraint(
            "payment_transaction_id",
            "entry_type",
            name="uq_credit_ledger_payment_entry_type",
        ),
    )

    wallet = db.relationship("Wallet", back_populates="ledger_entries")
    user = db.relationship("User", back_populates="ledger_entries")
    payment_transaction = db.relationship("PaymentTransaction", back_populates="ledger_entries")

    def __repr__(self):
        return f"<CreditLedgerEntry {self.entry_type} {self.amount_credits}>"


class GenerationRequest(db.Model):
    __tablename__ = "generation_requests"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    request_key = db.Column(db.String(255), unique=True, nullable=False, index=True)
    doc_type = db.Column(db.String(64), nullable=False)
    input_hash = db.Column(db.String(255), nullable=False)
    response_payload = db.Column(db.JSON, nullable=True)
    status = db.Column(db.String(32), nullable=False, default="pending")
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    user = db.relationship("User", back_populates="generation_requests")

    def __repr__(self):
        return f"<GenerationRequest {self.request_key} {self.status}>"


def get_or_create_wallet(user_id: int, currency: str = "USD") -> Wallet:
    wallet = Wallet.query.filter_by(user_id=user_id).first()
    if wallet is None:
        wallet = Wallet(user_id=user_id, currency=currency, balance_credits=0)
        db.session.add(wallet)
        db.session.commit()
    return wallet


def ensure_user(email: str, full_name: str | None = None, country_code: str | None = None) -> User:
    email = (email or "").strip().lower()
    if not email:
        raise ValueError("An email address is required for billing.")
    user = User.query.filter_by(email=email).first()
    if user is None:
        user = User(email=email, full_name=full_name, country_code=country_code or "KE")
        db.session.add(user)
        db.session.commit()
    return user


def seed_default_credit_packages():
    packages = [
        {"code": "starter", "name": "Starter Pack", "currency": "KES", "price_cents": 50000, "credit_units": 25},
        {"code": "growth", "name": "Growth Pack", "currency": "KES", "price_cents": 100000, "credit_units": 55},
        {"code": "pro", "name": "Pro Pack", "currency": "KES", "price_cents": 200000, "credit_units": 120},
    ]
    for item in packages:
        existing = CreditPackage.query.filter_by(code=item["code"]).first()
        if existing is None:
            db.session.add(
                CreditPackage(
                    code=item["code"],
                    name=item["name"],
                    description=f"{item['credit_units']} credits",
                    currency=item["currency"],
                    price_cents=item["price_cents"],
                    credit_units=item["credit_units"],
                    is_active=True,
                    sort_order=packages.index(item),
                )
            )
    db.session.commit()
    return CreditPackage.query.filter_by(is_active=True).order_by(CreditPackage.sort_order).all()


__all__ = [
    "User",
    "Wallet",
    "CreditPackage",
    "PaymentTransaction",
    "CreditLedgerEntry",
    "GenerationRequest",
    "get_or_create_wallet",
    "ensure_user",
    "seed_default_credit_packages",
]
