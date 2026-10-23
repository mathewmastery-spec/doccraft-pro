from __future__ import annotations

import hashlib
import hmac
import json
import os
import time
import urllib.error
import urllib.parse as parse
import urllib.request
from typing import Any, Dict, Optional


class PaymentProviderError(RuntimeError):
    """Raised when a payment provider cannot safely complete an operation."""


def _http_json(method: str, url: str, *, headers: Optional[dict] = None,
               payload: Optional[dict] = None) -> dict:
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(url, data=data, headers=headers or {}, method=method)
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            result = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:500]
        raise PaymentProviderError(f"Payment provider returned HTTP {exc.code}: {detail}") from exc
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise PaymentProviderError(f"Payment provider request failed: {exc}") from exc
    if not isinstance(result, dict):
        raise PaymentProviderError("Payment provider returned an invalid response.")
    return result


def _http_form(method: str, url: str, form: dict, headers: Optional[dict] = None) -> dict:
    data = parse.urlencode(form).encode("utf-8")
    request = urllib.request.Request(url, data=data, headers=headers or {}, method=method)
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            result = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:500]
        raise PaymentProviderError(f"Payment provider returned HTTP {exc.code}: {detail}") from exc
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise PaymentProviderError(f"Payment provider request failed: {exc}") from exc
    if not isinstance(result, dict):
        raise PaymentProviderError("Payment provider returned an invalid response.")
    return result


class PaymentProviderAdapter:
    provider_name = "base"

    def __init__(self):
        self.mode = (os.getenv("PAYMENT_PROVIDER_MODE") or "sandbox").lower()

    def create_checkout_session(self, *, amount_cents: int, currency: str,
                                customer_email: str, metadata: Optional[dict] = None,
                                package_code: Optional[str] = None,
                                reference: Optional[str] = None) -> Dict[str, Any]:
        raise NotImplementedError

    def verify_payment(self, *, payment_reference: str, **kwargs) -> Dict[str, Any]:
        raise NotImplementedError

    def verify_webhook(self, *, raw_body: bytes, signature: Optional[str],
                       headers: Optional[dict] = None) -> Dict[str, Any]:
        raise NotImplementedError


class PaystackProvider(PaymentProviderAdapter):
    provider_name = "paystack"

    def __init__(self):
        super().__init__()
        self.secret_key = os.getenv("PAYSTACK_SECRET_KEY")
        self.webhook_secret = os.getenv("PAYSTACK_WEBHOOK_SECRET") or self.secret_key

    def _require_secret(self):
        if not self.secret_key:
            raise PaymentProviderError("PAYSTACK_SECRET_KEY is not configured; payments are disabled.")

        # A live checkout must never silently run with Paystack test credentials.
        billing_enabled = (os.getenv("BILLING_ENABLED") or "false").strip().lower() == "true"
        app_base_url = (os.getenv("APP_BASE_URL") or "").strip().lower()
        is_production_url = app_base_url.startswith("https://") and "localhost" not in app_base_url
        if billing_enabled and is_production_url and self.secret_key.startswith("sk_test_"):
            raise PaymentProviderError(
                "Production billing is enabled but PAYSTACK_SECRET_KEY is a test key. "
                "Set the approved Paystack live secret key in the hosting environment."
            )

    def create_checkout_session(self, *, amount_cents: int, currency: str,
                                customer_email: str, metadata: Optional[dict] = None,
                                package_code: Optional[str] = None,
                                reference: Optional[str] = None) -> Dict[str, Any]:
        self._require_secret()
        base_url = (os.getenv("APP_BASE_URL") or "").rstrip("/")
        if not base_url:
            raise PaymentProviderError("APP_BASE_URL must be configured for Paystack checkout.")
        ref = reference or f"doccraft_{int(time.time())}_{os.urandom(6).hex()}"
        payload = {
            "email": customer_email,
            "amount": int(amount_cents),
            "currency": currency.upper(),
            "reference": ref,
            "callback_url": f"{base_url}/?payment=success&reference={parse.quote(ref)}",
            "metadata": {"package_code": package_code or "", **(metadata or {})},
        }
        result = _http_json(
            "POST", "https://api.paystack.co/transaction/initialize",
            headers={"Authorization": f"Bearer {self.secret_key}", "Content-Type": "application/json", "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"},
            payload=payload,
        )
        data = result.get("data") or {}
        if result.get("status") is not True or not data.get("authorization_url") or not data.get("reference"):
            raise PaymentProviderError("Paystack did not create a valid checkout session.")
        return {
            "id": str(data["reference"]), "provider": self.provider_name,
            "reference": str(data["reference"]), "status": "pending",
            "url": data["authorization_url"], "amount_cents": int(amount_cents),
            "currency": currency.upper(), "customer_email": customer_email,
            "metadata": payload["metadata"], "package_code": package_code,
        }

    def verify_payment(self, *, payment_reference: str, **kwargs) -> Dict[str, Any]:
        self._require_secret()
        ref = parse.quote(str(payment_reference), safe="")
        result = _http_json(
            "GET", f"https://api.paystack.co/transaction/verify/{ref}",
            headers={"Authorization": f"Bearer {self.secret_key}", "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"},
        )
        data = result.get("data") or {}
        paid = result.get("status") is True and data.get("status") == "success"
        return {
            "status": "succeeded" if paid else "failed",
            "reference": data.get("reference"), "provider": self.provider_name,
            "amount_cents": int(data.get("amount") or 0),
            "currency": str(data.get("currency") or "").upper(),
            "paid_at": data.get("paid_at"),
            "metadata": data.get("metadata") or {},
        }

    def verify_webhook(self, *, raw_body: bytes, signature: Optional[str],
                       headers: Optional[dict] = None) -> Dict[str, Any]:
        if not self.webhook_secret or not signature:
            raise ValueError("Paystack webhook secret/signature is missing.")
        expected = hmac.new(self.webhook_secret.encode(), raw_body, hashlib.sha512).hexdigest()
        if not hmac.compare_digest(expected, signature.strip()):
            raise ValueError("Invalid Paystack webhook signature.")
        try:
            event = json.loads(raw_body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError("Invalid webhook JSON.") from exc
        if not isinstance(event, dict):
            raise ValueError("Invalid webhook payload.")
        return event


class StripeProvider(PaymentProviderAdapter):
    provider_name = "stripe"

    def __init__(self):
        super().__init__()
        self.secret_key = os.getenv("STRIPE_SECRET_KEY")
        self.webhook_secret = os.getenv("STRIPE_WEBHOOK_SECRET")

    def _require_secret(self):
        if not self.secret_key:
            raise PaymentProviderError("STRIPE_SECRET_KEY is not configured; payments are disabled.")

    def create_checkout_session(self, *, amount_cents: int, currency: str,
                                customer_email: str, metadata: Optional[dict] = None,
                                package_code: Optional[str] = None,
                                reference: Optional[str] = None) -> Dict[str, Any]:
        self._require_secret()
        base_url = (os.getenv("APP_BASE_URL") or "").rstrip("/")
        if not base_url.startswith("https://") and self.mode == "live":
            raise PaymentProviderError("APP_BASE_URL must be HTTPS for live payments.")
        if not base_url:
            raise PaymentProviderError("APP_BASE_URL must be configured for Stripe checkout.")
        meta = {"package_code": package_code or "", "doccraft_reference": reference or "", **(metadata or {})}
        form = {
            "mode": "payment",
            "customer_email": customer_email,
            "success_url": f"{base_url}/?payment=success&session_id={{CHECKOUT_SESSION_ID}}",
            "cancel_url": f"{base_url}/?payment=cancelled",
            "line_items[0][price_data][currency]": currency.lower(),
            "line_items[0][price_data][unit_amount]": str(int(amount_cents)),
            "line_items[0][price_data][product_data][name]": f"DocCraft {package_code or 'Credit'} package",
            "line_items[0][quantity]": "1",
        }
        for key, value in meta.items():
            if value is not None and isinstance(value, (str, int, float, bool)):
                form[f"metadata[{key}]"] = str(value)
        result = _http_form(
            "POST", "https://api.stripe.com/v1/checkout/sessions", form,
            {"Authorization": f"Bearer {self.secret_key}", "Content-Type": "application/x-www-form-urlencoded"},
        )
        if not result.get("id") or not result.get("url"):
            raise PaymentProviderError("Stripe did not create a valid checkout session.")
        return {
            "id": str(result["id"]), "provider": self.provider_name,
            "reference": str(result["id"]), "status": "pending", "url": result["url"],
            "amount_cents": int(amount_cents), "currency": currency.upper(),
            "customer_email": customer_email, "metadata": meta, "package_code": package_code,
        }

    def verify_payment(self, *, payment_reference: str, **kwargs) -> Dict[str, Any]:
        self._require_secret()
        ref = parse.quote(str(payment_reference), safe="")
        result = _http_json(
            "GET", f"https://api.stripe.com/v1/checkout/sessions/{ref}",
            headers={"Authorization": f"Bearer {self.secret_key}"},
        )
        paid = result.get("payment_status") == "paid" and result.get("status") == "complete"
        return {
            "status": "succeeded" if paid else "failed",
            "reference": result.get("id"), "provider": self.provider_name,
            "amount_cents": int(result.get("amount_total") or 0),
            "currency": str(result.get("currency") or "").upper(),
            "paid_at": None, "metadata": result.get("metadata") or {},
        }

    def verify_webhook(self, *, raw_body: bytes, signature: Optional[str],
                       headers: Optional[dict] = None) -> Dict[str, Any]:
        if not self.webhook_secret or not signature:
            raise ValueError("Stripe webhook secret/signature is missing.")
        parts = {}
        for item in signature.split(","):
            key, sep, value = item.partition("=")
            if sep:
                parts.setdefault(key.strip(), []).append(value.strip())
        timestamps, signatures = parts.get("t", []), parts.get("v1", [])
        if not timestamps or not signatures:
            raise ValueError("Malformed Stripe signature.")
        timestamp = timestamps[0]
        try:
            timestamp_int = int(timestamp)
        except ValueError as exc:
            raise ValueError("Malformed Stripe timestamp.") from exc
        if abs(int(time.time()) - timestamp_int) > 300:
            raise ValueError("Expired Stripe webhook signature.")
        signed_payload = timestamp.encode() + b"." + raw_body
        expected = hmac.new(self.webhook_secret.encode(), signed_payload, hashlib.sha256).hexdigest()
        if not any(hmac.compare_digest(expected, candidate) for candidate in signatures):
            raise ValueError("Invalid Stripe webhook signature.")
        try:
            event = json.loads(raw_body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError("Invalid webhook JSON.") from exc
        if not isinstance(event, dict):
            raise ValueError("Invalid webhook payload.")
        return event


class TestPaymentProvider(PaymentProviderAdapter):
    """Deterministic fake provider used only when Flask TESTING=True."""
    provider_name = "test"

    def create_checkout_session(self, *, amount_cents: int, currency: str,
                                customer_email: str, metadata: Optional[dict] = None,
                                package_code: Optional[str] = None,
                                reference: Optional[str] = None) -> Dict[str, Any]:
        ref = reference or f"test_{os.urandom(8).hex()}"
        return {
            "id": ref, "provider": self.provider_name, "reference": ref,
            "status": "pending", "url": f"https://payments.invalid/checkout/{ref}",
            "amount_cents": int(amount_cents), "currency": currency.upper(),
            "customer_email": customer_email,
            "metadata": {"package_code": package_code or "", **(metadata or {})},
            "package_code": package_code,
        }

    def verify_payment(self, *, payment_reference: str, **kwargs) -> Dict[str, Any]:
        # This adapter is never selected in production.
        return {
            "status": "succeeded", "reference": str(payment_reference),
            "provider": self.provider_name, "amount_cents": int(kwargs.get("amount_cents") or 0),
            "currency": str(kwargs.get("currency") or "KES").upper(),
            "paid_at": None, "metadata": kwargs.get("metadata") or {},
        }

    def verify_webhook(self, *, raw_body: bytes, signature: Optional[str],
                       headers: Optional[dict] = None) -> Dict[str, Any]:
        try:
            event = json.loads(raw_body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError("Invalid webhook JSON.") from exc
        if not isinstance(event, dict):
            raise ValueError("Invalid webhook payload.")
        return event


def get_provider_adapter(*, testing: bool = False) -> PaymentProviderAdapter:
    # Never allow test success behavior outside an explicitly testing Flask app.
    if testing:
        return TestPaymentProvider()
    provider = (os.getenv("PAYMENT_PROVIDER") or "paystack").lower()
    if provider == "stripe":
        return StripeProvider()
    if provider == "paystack":
        return PaystackProvider()
    raise PaymentProviderError(f"Unsupported PAYMENT_PROVIDER: {provider}")
