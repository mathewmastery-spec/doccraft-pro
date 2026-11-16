from models import User, Wallet
import auth_routes


def test_workspace_and_wallet_require_verified_account(client):
    assert client.get("/").status_code == 302
    assert client.get("/api/wallet/balance").status_code == 401


def test_registration_verifies_existing_wallet_and_ignores_submitted_email(client, app, monkeypatch):
    sent = {}
    monkeypatch.setattr(auth_routes, "_send_verification", lambda email, token: sent.update(email=email, token=token))
    with app.app_context():
        user = User(email="owner@example.com", full_name="Wallet Owner", country_code="KE")
        app.extensions["sqlalchemy"].session.add(user)
        app.extensions["sqlalchemy"].session.flush()
        wallet = Wallet(user_id=user.id, currency="KES", balance_credits=27)
        app.extensions["sqlalchemy"].session.add(wallet)
        app.extensions["sqlalchemy"].session.commit()

    response = client.post("/api/auth/register", json={
        "email": "owner@example.com",
        "password": "a-secure-test-password",
    })
    assert response.status_code == 200
    assert sent["email"] == "owner@example.com"

    verified = client.get("/auth/verify", query_string={"token": sent["token"]})
    assert verified.status_code == 302

    balance = client.post("/api/wallet/balance", json={"email": "attacker@example.com"})
    assert balance.status_code == 200
    assert balance.get_json()["email"] == "owner@example.com"
    assert balance.get_json()["credits_balance"] == 27


def test_unverified_account_cannot_sign_in(client, monkeypatch):
    monkeypatch.setattr(auth_routes, "_send_verification", lambda email, token: None)
    response = client.post("/api/auth/register", json={
        "email": "pending@example.com",
        "password": "a-secure-test-password",
    })
    assert response.status_code == 200
    client.post("/api/auth/logout", json={})
    login = client.post("/api/auth/login", json={
        "email": "pending@example.com",
        "password": "a-secure-test-password",
    })
    assert login.status_code == 403
