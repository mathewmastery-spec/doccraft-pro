import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent


def _database_url() -> str:
    url = os.getenv("DATABASE_URL") or os.getenv("SQLALCHEMY_DATABASE_URI")
    if not url:
        if os.getenv("FLASK_ENV") == "production" or os.getenv("APP_ENV") == "production":
            raise RuntimeError("DATABASE_URL must be set in production.")
        url = "sqlite:///doccraft.db"
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)
    return url


def _secret_key() -> str:
    secret_key = os.getenv("SECRET_KEY")
    if not secret_key:
        if os.getenv("FLASK_ENV") == "production" or os.getenv("APP_ENV") == "production":
            raise RuntimeError("SECRET_KEY must be set in production.")
        return "dev-secret-change-me"
    insecure_values = {"dev-secret-change-me", "change-me", "secret", "development-secret", "test-secret", "flask-secret-key"}
    if secret_key in insecure_values and (os.getenv("FLASK_ENV") == "production" or os.getenv("APP_ENV") == "production"):
        raise RuntimeError("SECRET_KEY is insecure for production. Set a long random value in the environment.")
    return secret_key


class Config:
    SECRET_KEY = _secret_key()
    SQLALCHEMY_DATABASE_URI = _database_url()
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    # Validate pooled connections before reuse and recycle periodically.
    SQLALCHEMY_ENGINE_OPTIONS = {"pool_pre_ping": True, "pool_recycle": 300}
    AI_PROVIDER = os.getenv("AI_PROVIDER", "openai").strip().lower()
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
    GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.8-flash")
    PAYMENT_PROVIDER = (os.getenv("PAYMENT_PROVIDER") or "paystack").lower()
    PAYMENT_PROVIDER_MODE = os.getenv("PAYMENT_PROVIDER_MODE", "sandbox")
    APP_BASE_URL = os.getenv("APP_BASE_URL", "http://localhost:5000")
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
    BILLING_ENABLED = os.getenv("BILLING_ENABLED", "false").lower() == "true"
    DOCCRAFT_FREE_GENERATIONS = int(os.getenv("DOCCRAFT_FREE_GENERATIONS", "0"))
    DOC_CREDIT_COST = int(os.getenv("DOC_CREDIT_COST", "1"))
    DOC_ACTION_CREDIT_COST = int(os.getenv("DOC_ACTION_CREDIT_COST", "1"))
    PAYSTACK_SECRET_KEY = os.getenv("PAYSTACK_SECRET_KEY")
    PAYSTACK_PUBLIC_KEY = os.getenv("PAYSTACK_PUBLIC_KEY")
    PAYSTACK_WEBHOOK_SECRET = os.getenv("PAYSTACK_WEBHOOK_SECRET")
    STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY")
    STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET")
    TESTING = False


class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = os.getenv("TEST_DATABASE_URL", "sqlite:///:memory:")
    PRESERVE_CONTEXT_ON_EXCEPTION = False


config = Config
