import pytest

from payment_provider import PaystackProvider, PaymentProviderError


def test_production_billing_rejects_paystack_test_key(monkeypatch):
    monkeypatch.setenv("BILLING_ENABLED", "true")
    monkeypatch.setenv("APP_BASE_URL", "https://doccraft-pro.onrender.com")

    provider = PaystackProvider()
    provider.secret_key = "sk_test_example"
    with pytest.raises(PaymentProviderError, match="test key"):
        provider._require_secret()


def test_production_billing_accepts_live_key_format(monkeypatch):
    monkeypatch.setenv("BILLING_ENABLED", "true")
    monkeypatch.setenv("APP_BASE_URL", "https://doccraft-pro.onrender.com")

    provider = PaystackProvider()
    provider.secret_key = "sk_live_example"
    provider._require_secret()


def test_nonproduction_can_use_test_key(monkeypatch):
    monkeypatch.setenv("BILLING_ENABLED", "true")
    monkeypatch.setenv("APP_BASE_URL", "http://localhost:5000")

    provider = PaystackProvider()
    provider.secret_key = "sk_test_example"
    provider._require_secret()
