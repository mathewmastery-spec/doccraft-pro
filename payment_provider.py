from __future__ import annotations

import hashlib
import hmac
import json
import os
import time
import uuid
from typing import Any, Dict, Optional
from urllib import error, request


class PaymentProviderAdapter:
    provider_name = "mock"

    def __init__(self):
        self.mode = os.getenv("PAYMENT_PROVIDER_MODE", "sandbox")

    def create_checkout_session(self, *, amount_cents: int, currency: str, customer_email: str, metadata: Optional[dict] = None, package_code: Optional[str] = None):
        return {
            "id": f"mock_session_{uuid.uuid4().hex[:16]}",
            "provider": self.provider_name,
            "reference": f"mock_ref_{uuid.uuid4().hex[:16]}",
            "status": "pending",
            "url": f"/sandbox/payments/{self.provider_name}/checkout/{uuid.uuid4().hex[:8]}",
            "amount_cents": int(amount_cents),
            "currency": currency.upper(),
            "customer_email": customer_email,
            "metadata": metadata or {},
            "package_code": package_code,
        }

    def verify_payment(self, *, payment_reference: str, **kwargs):
        return {
            "status": "succeeded",
            "reference": payment_reference,
            "provider": self.provider_name,
            "amount_cents": int(kwargs.get("amount_cents", 0) or 0),
            "currency": (kwargs.get("currency") or "KES").upper(),
            "paid_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }

    def verify_webhook(self, *, raw_body: bytes, signature: Optional[str], headers: Optional[dict] = None) -> Dict[str, Any]:
        return json.loads(raw_body.decode("utf-8"))


class PaystackProvider(PaymentProviderAdapter):
    provider_name = "paystack"

    def __init__(self):
        super().__init__()
        self.secret_key = os.getenv("PAYSTACK_SECRET_KEY")
        self.webhook_secret = os.getenv("PAYSTACK_WEBHOOK_SECRET")

    def create_checkout_session(self, *, amount_cents: int, currency: str, customer_email: str, metadata: Optional[dict] = None, package_code: Optional[str] = None):
        if not self.secret_key:
            return super().create_checkout_session(amount_cents=amount_cents, currency=currency, customer_email=customer_email, metadata=metadata, package_code=package_code)
        reference = f"paystack_{uuid.uuid4().hex[:16]}"
        payload = {
            "email": customer_email,
            "amount": int(amount_cents),
            "currency": currency.upper(),
            "reference": reference,
            "callback_url": os.getenv("APP_BASE_URL", "http://localhost:5000") + "/billing/checkout/callback",
            "metadata": {"package_code": package_code or "", **(metadata or {})},
        }
        raw_result = _http_json(
            "POST",
            "https://api.paystack.co/transaction/initialize",
            payload=payload,
            headers={"Authorization": f"Bearer {self.secret_key}", "Content-Type": "application/json"},
        )
        if raw_result.get("status") is False or "error" in raw_result:
            return super().create_checkout_session(amount_cents=amount_cents, currency=currency, customer_email=customer_email, metadata=metadata, package_code=package_code)
        data = raw_result.get("data") or {}
        return {
            "id": str(data.get("reference") or reference),
            "provider": self.provider_name,
            "reference": str(data.get("reference") or reference),
            "status": "pending",
            "url": data.get("authorization_url") or "/sandbox/payments/paystack/checkout",
            "amount_cents": int(amount_cents),
            "currency": currency.upper(),
            "customer_email": customer_email,
            "metadata": metadata or {},
            "package_code": package_code,
        }

    def verify_payment(self, *, payment_reference: str, **kwargs):
        if not self.secret_key:
            return super().verify_payment(payment_reference=payment_reference, **kwargs)
        raw_result = _http_json(
            "GET",
            f"https://api.paystack.co/transaction/verify/{payment_reference}",
            headers={"Authorization": f"Bearer {self.secret_key}"},
        )
        if raw_result.get("status") is False or "error" in raw_result:
            return {"status": "failed", "reference": payment_reference, "provider": self.provider_name}
        data = raw_result.get("data") or {}
        amount = int(data.get("amount", 0) or 0)
        return {
            "status": "succeeded" if data.get("status") in {"success", "successful"} else "failed",
            "reference": payment_reference,
            "provider": self.provider_name,
            "amount_cents": amount,
            "currency": (data.get("currency") or "KES").upper(),
            "paid_at": data.get("paid_at") or time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }

    def verify_webhook(self, *, raw_body: bytes, signature: Optional[str], headers: Optional[dict] = None) -> Dict[str, Any]:
        secret = self.webhook_secret or ""
        if secret and signature:
            digest = hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha512).hexdigest()
            if not hmac.compare_digest(digest, signature):
                raise ValueError("Invalid Paystack webhook signature")
        return json.loads(raw_body.decode("utf-8"))


class StripeProvider(PaymentProviderAdapter):
    provider_name = "stripe"

    def __init__(self):
        super().__init__()
        self.secret_key = os.getenv("STRIPE_SECRET_KEY")
        self.webhook_secret = os.getenv("STRIPE_WEBHOOK_SECRET")

    def create_checkout_session(self, *, amount_cents: int, currency: str, customer_email: str, metadata: Optional[dict] = None, package_code: Optional[str] = None):
        if not self.secret_key:
            return super().create_checkout_session(amount_cents=amount_cents, currency=currency, customer_email=customer_email, metadata=metadata, package_code=package_code)
        return {
            "id": f"stripe_session_{uuid.uuid4().hex[:16]}",
            "provider": self.provider_name,
            "status": "pending",
            "reference": f"stripe_{uuid.uuid4().hex[:16]}",
            "url": "/sandbox/payments/stripe/checkout",
            "amount_cents": int(amount_cents),
            "currency": currency.upper(),
            "customer_email": customer_email,
            "metadata": metadata or {},
            "package_code": package_code,
        }

    def verify_payment(self, *, payment_reference: str, **kwargs):
        if not self.secret_key:
            return super().verify_payment(payment_reference=payment_reference, **kwargs)
        return {
            "status": "succeeded",
            "reference": payment_reference,
            "provider": self.provider_name,
            "amount_cents": int(kwargs.get("amount_cents", 0) or 0),
            "currency": (kwargs.get("currency") or "KES").upper(),
            "paid_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }

    def verify_webhook(self, *, raw_body: bytes, signature: Optional[str], headers: Optional[dict] = None) -> Dict[str, Any]:
        secret = self.webhook_secret or ""
        if secret and signature:
            timestamp, _, signed = signature.partition(",")
            if not timestamp:
                raise ValueError("Invalid Stripe signature")
            payload = f"{timestamp}.{raw_body.decode('utf-8')}"
            digest = hmac.new(secret.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).hexdigest()
            v1 = signed.split("=")[-1]
            if not hmac.compare_digest(digest, v1):
                raise ValueError("Invalid Stripe webhook signature")
        return json.loads(raw_body.decode("utf-8"))


def _http_json(method: str, url: str, payload: Optional[dict] = None, headers: Optional[dict] = None):
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    req = request.Request(url, data=data, headers=headers or {}, method=method)
    try:
        with request.urlopen(req, timeout=20) as response:
            return json.loads(response.read().decode("utf-8"))
    except error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        return {"error": body, "status_code": exc.code}
    except error.URLError as exc:
        return {"error": str(exc), "status_code": 0}


def get_provider_adapter() -> PaymentProviderAdapter:
    provider = (os.getenv("PAYMENT_PROVIDER") or "paystack").lower()
    if provider == "stripe":
        return StripeProvider()
    if provider == "paystack":
        return PaystackProvider()
    return PaymentProviderAdapter()
