import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent


def _database_url() -> str:
    url = os.getenv("DATABASE_URL") or os.getenv("SQLALCHEMY_DATABASE_URI") or "sqlite:///doccraft.db"
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)
    return url


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-change-me")
    SQLALCHEMY_DATABASE_URI = _database_url()
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    PAYMENT_PROVIDER = os.getenv("PAYMENT_PROVIDER", "stripe")
    PAYMENT_PROVIDER_MODE = os.getenv("PAYMENT_PROVIDER_MODE", "sandbox")
    APP_BASE_URL = os.getenv("APP_BASE_URL", "http://localhost:5000")
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
    DOCCRAFT_FREE_GENERATIONS = int(os.getenv("DOCCRAFT_FREE_GENERATIONS", "0"))


config = Config
