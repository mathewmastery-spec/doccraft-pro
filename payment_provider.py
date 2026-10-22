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
