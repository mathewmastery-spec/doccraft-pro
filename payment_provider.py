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
                                package_code: Optional[str] = None) -> Dict[str, Any]:
        self._require_secret()
        base_url = (os.getenv("APP_BASE_URL") or "").rstrip("/")
        if not base_url.startswith("https://") and self.mode == "live":
            raise PaymentProviderError("APP_BASE_URL must be HTTPS for live payments.")
        if not base_url:
            raise PaymentProviderError("APP_BASE_URL must be configured for Stripe checkout.")
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
        for key, value in {"package_code": package_code or "", **(metadata or {})}.items():
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
            "customer_email": customer_email,
            "metadata": {"package_code": package_code or "", **(metadata or {})},
            "package_code": package_code,
        }

    def verify_payment(self, *, payment_reference: str, **kwargs) -> Dict[str, Any]:
        self._require_secret()
        result = _http_json(
            "GET", f"https://api.stripe.com/v1/checkout/sessions/{parse.quote(str(payment_reference), safe='')}",
            headers={"Authorization": f"Bearer {self.secret_key}"},
        )
        return {
            "status": "succeeded" if result.get("payment_status") == "paid" and result.get("status") == "complete" else "failed",
            "reference": result.get("id"), "provider": self.provider_name,
            "amount_cents": int(result.get("amount_total") or 0),
            "currency": str(result.get("currency") or "").upper(),
            "paid_at": None,
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
        timestamps = parts.get("t", [])
        signatures = parts.get("v1", [])
        if not timestamps or not signatures:
            raise ValueError("Malformed Stripe signature.")
        timestamp = timestamps[0]
        try:
            timestamp_int = int(timestamp)
        except ValueError as exc:
            raise ValueError("Malformed Stripe timestamp.") from exc
        # Reject old signatures to limit replay attacks.
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


def get_provider_adapter() -> PaymentProviderAdapter:
    provider = (os.getenv("PAYMENT_PROVIDER") or "paystack").lower()
    if provider == "stripe":
        return StripeProvider()
    if provider == "paystack":
        return PaystackProvider()
    raise PaymentProviderError(f"Unsupported PAYMENT_PROVIDER: {provider}")
