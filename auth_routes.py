from __future__ import annotations

import hashlib
import os
import secrets
import smtplib
import json
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage

from flask import Blueprint, current_app, jsonify, redirect, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from extensions import db
from models import AuthAccount, AuthToken, User

auth_bp = Blueprint("auth_bp", __name__)
TOKEN_MINUTES = 30


def authenticated_user():
    user_id = session.get("doccraft_user_id")
    user = db.session.get(User, user_id) if user_id else None
    account = AuthAccount.query.filter_by(user_id=user.id).first() if user else None
    if not user or not user.is_active or not account or not account.email_verified:
        return None
    return user


def _valid_email(value):
    email = str(value or "").strip().lower()
    return email if len(email) <= 254 and "@" in email and "." in email.rsplit("@", 1)[-1] else ""


def _send_verification(email, token):
    """Send a single-use verification link through the configured transactional provider."""
    cfg = current_app.config
    base = str(cfg.get("APP_BASE_URL") or os.getenv("APP_BASE_URL") or request.url_root).rstrip("/")
    link = base + url_for("auth_bp.verify_email", token=token)
    subject = "Verify your DocCraft Pro account"
    text_body = (
        "Welcome to DocCraft Pro. Verify that you own this email address using the link below.\n\n"
        + link + "\n\nThis link expires in 30 minutes and can only be used once. "
        "If you did not request this, you can ignore this message."
    )

    provider = str(cfg.get("EMAIL_PROVIDER") or "resend").strip().lower()
    if provider == "resend":
        api_key = cfg.get("RESEND_API_KEY")
        sender = cfg.get("MAIL_DEFAULT_SENDER")
        if not api_key or not sender:
            raise RuntimeError("Resend email delivery is not configured. Set RESEND_API_KEY and MAIL_DEFAULT_SENDER.")
        payload = json.dumps({
            "from": sender,
            "to": [email],
            "subject": subject,
            "text": text_body,
        }).encode("utf-8")
        req = urllib.request.Request(
            "https://api.resend.com/emails",
            data=payload,
            headers={
                "Authorization": "Bearer " + str(api_key),
                "Content-Type": "application/json",
                "User-Agent": "DocCraft-Pro/1.0",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=20) as response:
                if response.status < 200 or response.status >= 300:
                    raise RuntimeError("Email provider rejected the verification message.")
        except urllib.error.HTTPError as exc:
            # Do not log request headers or credentials.
            detail = exc.read(1000).decode("utf-8", "replace")
            current_app.logger.error("Resend rejected verification email (HTTP %s): %s", exc.code, detail)
            raise RuntimeError("The email provider rejected the verification message.") from None
        except urllib.error.URLError as exc:
            current_app.logger.error("Resend verification request failed: %s", getattr(exc, "reason", "network error"))
            raise RuntimeError("Could not reach the email provider over HTTPS.") from None
        return

    if provider != "smtp":
        raise RuntimeError("EMAIL_PROVIDER must be set to 'resend' or 'smtp'.")
    username = cfg.get("MAIL_USERNAME")
    password = cfg.get("MAIL_PASSWORD")
    sender = cfg.get("MAIL_DEFAULT_SENDER") or username
    if not username or not password or not sender:
        raise RuntimeError("SMTP email delivery is not configured.")
    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = sender
    message["To"] = email
    message.set_content(text_body)
    with smtplib.SMTP(cfg.get("MAIL_SERVER", "smtp.gmail.com"), int(cfg.get("MAIL_PORT", 587)), timeout=20) as smtp:
        if cfg.get("MAIL_USE_TLS", True):
            smtp.starttls()
        smtp.login(username, password)
        smtp.send_message(message)


def _issue_verification(user, account):
    raw = secrets.token_urlsafe(32)
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    AuthToken.query.filter_by(user_id=user.id, purpose="verify_email").delete()
    db.session.add(AuthToken(
        user_id=user.id,
        token_hash=digest,
        purpose="verify_email",
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=TOKEN_MINUTES),
    ))
    db.session.commit()
    try:
        _send_verification(user.email, raw)
    except Exception:
        db.session.rollback()
        current_app.logger.exception("DocCraft verification email could not be sent")
        return False
    return True


@auth_bp.post("/api/auth/register")
def register():
    body = request.get_json(silent=True) or {}
    email = _valid_email(body.get("email"))
    password = str(body.get("password") or "")
    full_name = str(body.get("full_name") or "").strip()[:255]
    if not email or len(password) < 10 or len(password) > 128:
        return jsonify({"success": False, "error": "Enter a valid email and a password of at least 10 characters."}), 400

    user = User.query.filter_by(email=email).first()
    if user is None:
        user = User(email=email, full_name=full_name or None, country_code="KE")
        db.session.add(user)
        db.session.flush()
    account = AuthAccount.query.filter_by(user_id=user.id).first()
    if account and account.email_verified:
        return jsonify({"success": False, "error": "An account already exists. Please sign in or reset your password."}), 409
    if account is None:
        account = AuthAccount(user_id=user.id, password_hash=generate_password_hash(password), email_verified=False)
        db.session.add(account)
    else:
        account.password_hash = generate_password_hash(password)
    db.session.commit()
    if not _issue_verification(user, account):
        return jsonify({"success": False, "error": "Verification email could not be sent. Please check the email settings and try again."}), 503
    return jsonify({"success": True, "message": "Check your email for a verification link. It expires in 30 minutes."})


@auth_bp.get("/auth/verify")
def verify_email():
    raw = str(request.args.get("token") or "")
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    record = AuthToken.query.filter_by(token_hash=digest, purpose="verify_email").first()
    now = datetime.now(timezone.utc)
    if record is None:
        return "This verification link is invalid or has already been used.", 400
    expires = record.expires_at
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)
    if expires <= now:
        db.session.delete(record)
        db.session.commit()
        return "This verification link has expired. Return to DocCraft Pro and request another.", 400
    account = AuthAccount.query.filter_by(user_id=record.user_id).first()
    if account is None:
        return "This account could not be verified. Please register again.", 400
    verified_user_id = record.user_id
    account.email_verified = True
    db.session.delete(record)
    db.session.commit()
    session.clear()
    session["doccraft_user_id"] = verified_user_id
    session.permanent = True
    return redirect("/?account_verified=1")


@auth_bp.post("/api/auth/login")
def login():
    body = request.get_json(silent=True) or {}
    email = _valid_email(body.get("email"))
    password = str(body.get("password") or "")
    user = User.query.filter_by(email=email).first() if email else None
    account = AuthAccount.query.filter_by(user_id=user.id).first() if user else None
    if not account or not check_password_hash(account.password_hash, password):
        return jsonify({"success": False, "error": "Email or password is incorrect."}), 401
    if not account.email_verified:
        return jsonify({"success": False, "error": "Verify your email before signing in. Use the resend option if needed."}), 403
    if not user.is_active:
        return jsonify({"success": False, "error": "This account is inactive."}), 403
    session.clear()
    session["doccraft_user_id"] = user.id
    session.permanent = True
    return jsonify({"success": True, "user": {"email": user.email, "full_name": user.full_name}})


@auth_bp.post("/api/auth/resend-verification")
def resend_verification():
    body = request.get_json(silent=True) or {}
    email = _valid_email(body.get("email"))
    user = User.query.filter_by(email=email).first() if email else None
    account = AuthAccount.query.filter_by(user_id=user.id).first() if user else None
    if account and not account.email_verified:
        if not _issue_verification(user, account):
            return jsonify({"success": False, "error": "Verification email could not be sent. Please try again later."}), 503
    return jsonify({"success": True, "message": "If the account needs verification, a new link has been sent."})


@auth_bp.get("/api/auth/session")
def auth_session():
    user_id = session.get("doccraft_user_id")
    user = db.session.get(User, user_id) if user_id else None
    account = AuthAccount.query.filter_by(user_id=user.id).first() if user else None
    if not user or not account or not account.email_verified or not user.is_active:
        session.pop("doccraft_user_id", None)
        return jsonify({"authenticated": False})
    return jsonify({"authenticated": True, "user": {"email": user.email, "full_name": user.full_name}})


@auth_bp.post("/api/auth/logout")
def logout():
    session.clear()
    return jsonify({"success": True})
