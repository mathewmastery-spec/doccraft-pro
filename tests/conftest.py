import pytest

from app import create_app
from extensions import db
from models import AuthAccount, User


@pytest.fixture
def app():
    app = create_app(test_config={"TESTING": True, "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:", "BILLING_ENABLED": True})
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    with app.app_context():
        user = User(email="test-session@example.com", full_name="Test Session")
        db.session.add(user)
        db.session.flush()
        db.session.add(AuthAccount(user_id=user.id, password_hash="test-only", email_verified=True))
        db.session.commit()
        user_id = user.id
    client = app.test_client()
    with client.session_transaction() as session:
        session["doccraft_user_id"] = user_id
    return client


@pytest.fixture
def anon_client(app):
    return app.test_client()
