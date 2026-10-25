from __future__ import annotations

import hashlib
import json
import os
import uuid

from flask import Flask, Response, jsonify, render_template, request, send_from_directory
from openai import OpenAI
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from billing_routes import billing_bp
from config import config
from extensions import db, migrate

SYSTEM_PROMPTS = {
    "resume": "You are an expert resume writer. Parse the user's input and return a JSON object with these fields:\n{\n  \"name\": \"\", \"email\": \"\", \"phone\": \"\", \"location\": \"\", \"linkedin\": \"\", \"website\": \"\", \"summary\": \"\", \"skills\": [], \"languages\": [], \"experience\": [], \"education\": [], \"certifications\": [], \"projects\": []\n}\n",
    "cv": "You are an expert CV writer. Return valid JSON with personal info, summary, skills, experience, education, languages, and certs.",
    "academic_cv": "You are a professional academic CV writer. Return valid JSON with personal info, research, teaching, publications, and education.",
    "cover_letter": "You are a professional cover letter writer. Return valid JSON containing subject and full_letter.",
    "portfolio": "You are a portfolio writer. Return valid JSON with personal info, bio, skills, projects, education, and achievements.",
    "org_letter": "You are a formal letter writer. Return valid JSON with subject and full_letter.",
}

REPLY_MESSAGES = {
    "resume": "Your resume has been generated! You can see it in the preview. Switch templates or edit the form to refine it.",
    "cv": "Your CV is ready in the preview panel. Feel free to refine it.",
    "academic_cv": "Your academic CV is ready in the preview panel.",
    "cover_letter": "Your cover letter is ready.",
    "portfolio": "Your portfolio is ready.",
    "org_letter": "Your formal letter is ready.",
}



def _request_fingerprint(doc_type: str, user_input: str, extra: object) -> str:
    """Stable fingerprint used to reject reuse of a key for different content."""
    canonical = json.dumps(
        {"doc_type": doc_type, "user_input": user_input, "extra": extra},
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=str,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def create_app(test_config=None):
    app = Flask(__name__)
    app.config.from_object(config)
    if test_config:
        app.config.update(test_config)

    db.init_app(app)
    migrate.init_app(app, db)
    app.register_blueprint(billing_bp)

    # One-time safe bootstrap for a newly provisioned database. SQLAlchemy's
    # create_all() creates missing tables without dropping existing tables.
    # Enable explicitly with AUTO_INIT_DB=true, then disable after first success.
    if os.getenv("AUTO_INIT_DB", "false").strip().lower() == "true":
        from models import seed_default_credit_packages

        with app.app_context():
            db.create_all()
            seed_default_credit_packages()

    @app.route("/")
    def home():
        response = Response(render_template("doccraft.html"), mimetype="text/html")
        # Prevent browsers and intermediary caches from keeping an outdated homepage.
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
        return response

    @app.route("/robots.txt")
    def robots_txt():
        return Response(
            "User-agent: *\nAllow: /\nDisallow: /api/\nDisallow: /health\n\n"
            "Sitemap: https://doccraft-pro.onrender.com/sitemap.xml\n",
            mimetype="text/plain",
        )

    @app.route("/sitemap.xml")
    def sitemap_xml():
        return Response(
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
            "  <url><loc>https://doccraft-pro.onrender.com/</loc></url>\n"
            "</urlset>\n",
            mimetype="application/xml",
        )

    @app.route("/doccraft-icon-192.png")
    @app.route("/doccraft-icon-512.png")
    def doccraft_icon():
        # The PWA icons currently live in the repository root.
        return send_from_directory(app.root_path, request.path.rsplit("/", 1)[-1], mimetype="image/png")

    @app.route("/service-worker.js")
    def service_worker():
        # Serve the worker at the site root so its default scope covers the app.
        response = send_from_directory("static", "service-worker.js", mimetype="application/javascript")
        response.headers["Service-Worker-Allowed"] = "/"
        response.headers["Cache-Control"] = "no-cache"
        return response

    @app.route("/health")
    def health():
        return jsonify({"status": "ok", "app": "DocCraft"})


    @app.route("/api/wallet/authorize-document", methods=["POST"])
    def authorize_document():
        """Authorize one form-built document; zero-credit users receive watermarked previews."""
        from models import GenerationRequest, ensure_user, get_or_create_wallet

        payload = request.get_json(silent=True) or {}
        email_value = payload.get("email") or ""
        email = email_value.strip().lower() if isinstance(email_value, str) else ""
        doc_type = payload.get("doc_type") or "resume"
        request_key = str(payload.get("request_id") or uuid.uuid4()).strip()
        content = payload.get("document")
        if not isinstance(content, dict) or doc_type not in SYSTEM_PROMPTS:
            return jsonify({"success": False, "error": "Invalid document request."}), 400
        if not email or "@" not in email or len(email) > 254:
            return jsonify({"success": False, "error": "Enter your account email in the Wallet to use document credits."}), 400
        if not app.config.get("BILLING_ENABLED", False):
            production_runtime = (
                str(os.getenv("RENDER", "")).strip().lower() == "true"
                or str(os.getenv("FLASK_ENV", "")).strip().lower() == "production"
                or str(os.getenv("APP_ENV", "")).strip().lower() == "production"
            )
            if production_runtime:
                return jsonify({"success": False, "error": "Document access is temporarily unavailable. Please try again later."}), 503
            return jsonify({"success": True, "preview_only": False, "wallet_balance": None})
        fingerprint = _request_fingerprint(doc_type, json.dumps(content, sort_keys=True, ensure_ascii=False, default=str), {})
        try:
            user = ensure_user(email, country_code="KE")
            if not user.is_active:
                return jsonify({"success": False, "error": "This account is inactive."}), 403
            existing = GenerationRequest.query.filter_by(request_key=request_key).first()
            if existing:
                if existing.user_id != user.id or existing.input_hash != fingerprint:
                    return jsonify({"success": False, "error": "This request was already used. Please retry."}), 409
                if existing.status == "succeeded" and isinstance(existing.response_payload, dict):
                    return jsonify(existing.response_payload)
                return jsonify({"success": False, "error": "This document request is still processing. Please retry."}), 409
            wallet = get_or_create_wallet(user.id, currency="KES")
            cost = int(app.config.get("DOC_CREDIT_COST", 1))
            preview_only = cost <= 0 or wallet.balance_credits < cost
            response_payload = {"success": True, "preview_only": preview_only, "wallet_balance": int(wallet.balance_credits)}
            generation = GenerationRequest(user_id=user.id, request_key=request_key, doc_type=doc_type, input_hash=fingerprint, status="pending")
            db.session.add(generation)
            db.session.flush()
            if not preview_only:
                wallet.spend_credits(cost, f"Form document generation: {doc_type}", user=user)
                response_payload["wallet_balance"] = int(wallet.balance_credits)
            generation.status = "succeeded"
            generation.response_payload = response_payload
            db.session.commit()
            return jsonify(response_payload)
        except IntegrityError:
            db.session.rollback()
            return jsonify({"success": False, "error": "This document request was already processed. Please retry."}), 409
        except Exception:
            db.session.rollback()
            app.logger.exception("DocCraft document authorization failed")
            return jsonify({"success": False, "error": "Could not verify document access. Please try again."}), 503

    @app.route("/api/generate", methods=["POST"])
    def generate():
        # Import locally so the existing application can still start even if a
        # migration temporarily leaves the billing models unavailable at import.
        from models import GenerationRequest, ensure_user, get_or_create_wallet

        payload = request.get_json(silent=True) or {}
        if not isinstance(payload, dict):
            return jsonify({"success": False, "error": "Invalid request body."}), 400

        doc_type = payload.get("doc_type", "resume")
        user_input = payload.get("user_input", "")
        extra = payload.get("extra") or {}
        request_key = payload.get("request_id") or payload.get("idempotency_key")

        if not isinstance(doc_type, str) or doc_type not in SYSTEM_PROMPTS:
            return jsonify({"success": False, "error": "Please select a valid document type."}), 400
        if not isinstance(user_input, str) or not user_input.strip():
            return jsonify({"success": False, "error": "Please enter your information."}), 400
        if not isinstance(extra, dict):
            return jsonify({"success": False, "error": "Invalid additional document data."}), 400

        email_value = payload.get("email") or payload.get("user_email") or ""
        email = email_value.strip().lower() if isinstance(email_value, str) else ""
        billing_enabled = bool(app.config.get("BILLING_ENABLED", False))
        # Fail closed on Render/production: a missing or false billing flag must
        # never silently turn paid document generation into a free service.
        production_runtime = (
            str(os.getenv("RENDER", "")).strip().lower() == "true"
            or str(os.getenv("FLASK_ENV", "")).strip().lower() == "production"
            or str(os.getenv("APP_ENV", "")).strip().lower() == "production"
        )
        if production_runtime and not billing_enabled:
            return jsonify({
                "success": False,
                "error": "Paid document generation is temporarily unavailable. Please try again later.",
            }), 503
        if billing_enabled and (not email or "@" not in email or len(email) > 254):
            return jsonify({"success": False, "error": "Enter a valid email address to use your credit wallet."}), 400
        if email and ("@" not in email or len(email) > 254):
            return jsonify({"success": False, "error": "Please enter a valid email address."}), 400

        api_key = app.config.get("OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY")
        if not api_key:
            return jsonify({"success": False, "error": "Generation is not configured yet."}), 503

        if request_key is None or not str(request_key).strip():
            request_key = str(uuid.uuid4())
        else:
            request_key = str(request_key).strip()
        if len(request_key) > 255:
            return jsonify({"success": False, "error": "The request ID is too long."}), 400

        fingerprint = _request_fingerprint(doc_type, user_input.strip(), extra)
        user = None
        wallet = None
        try:
            if email:
                user = ensure_user(
                    email,
                    full_name=payload.get("full_name"),
                    country_code=payload.get("country_code") or "KE",
                )
                if not user.is_active:
                    return jsonify({"success": False, "error": "This account is inactive."}), 403
                if billing_enabled:
                    wallet = get_or_create_wallet(user.id, currency="KES")
                    if (wallet.status or "active").lower() != "active":
                        return jsonify({"success": False, "error": "Your credit wallet is inactive."}), 403

            # Return a completed response for a retried request. A request key
            # cannot be reused for different content or another user's account.
            generation = GenerationRequest.query.filter_by(request_key=request_key).first()
            if generation is not None:
                same_user = generation.user_id == (user.id if user else None)
                if not same_user or generation.input_hash != fingerprint:
                    return jsonify({"success": False, "error": "This request ID was already used for different content. Start a new request."}), 409
                if generation.status == "succeeded" and isinstance(generation.response_payload, dict):
                    return jsonify(generation.response_payload)
                if generation.status == "pending":
                    return jsonify({"success": False, "error": "This request is already being processed. Please wait before retrying."}), 409
                # A prior attempt failed before a result was saved; allow a retry.
                generation.status = "pending"
                generation.response_payload = None
                db.session.commit()
            else:
                generation = GenerationRequest(
                    user_id=user.id if user else None,
                    request_key=request_key,
                    doc_type=doc_type,
                    input_hash=fingerprint,
                    status="pending",
                )
                db.session.add(generation)
                try:
                    db.session.commit()
                except IntegrityError:
                    # Another simultaneous request may have claimed this key.
                    db.session.rollback()
                    existing = GenerationRequest.query.filter_by(request_key=request_key).first()
                    if existing and existing.user_id == (user.id if user else None) and existing.input_hash == fingerprint:
                        if existing.status == "succeeded" and isinstance(existing.response_payload, dict):
                            return jsonify(existing.response_payload)
                        return jsonify({"success": False, "error": "This request is already being processed. Please wait before retrying."}), 409
                    return jsonify({"success": False, "error": "This request ID was already used. Start a new request."}), 409

            if billing_enabled:
                # Re-check balance immediately before generation. The actual
                # debit is committed with the saved result after successful AI output.
                wallet = get_or_create_wallet(user.id, currency="KES")
                cost = int(app.config.get("DOC_CREDIT_COST", 1))
                if cost <= 0:
                    generation.status = "failed"
                    db.session.commit()
                    return jsonify({"success": False, "error": "Document credit cost is misconfigured."}), 503
                preview_only = wallet.balance_credits < cost
            else:
                preview_only = False

            context = ""
            if extra.get("currentData"):
                context = "\n\nExisting data to merge with:\n" + json.dumps(extra["currentData"], ensure_ascii=False, default=str)

            client = OpenAI(api_key=api_key)
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPTS[doc_type]},
                    {"role": "user", "content": user_input.strip() + context},
                ],
                temperature=0.7,
                max_tokens=2000,
                response_format={"type": "json_object"},
            )
            raw = (response.choices[0].message.content or "").strip()
            if raw.startswith("```"):
                raw = raw.split("\n", 1)[-1]
                if raw.endswith("```"):
                    raw = raw[:-3]
            data = json.loads(raw.strip())
            if not isinstance(data, dict):
                raise ValueError("The generation provider returned an invalid document format.")

            result = {
                "success": True,
                "data": data,
                "reply": REPLY_MESSAGES[doc_type],
                "request_id": request_key,
                "preview_only": bool(preview_only),
                "wallet_balance": int(wallet.balance_credits) if wallet is not None else None,
            }

            if billing_enabled and not preview_only:
                # Debit and persist the successful response in one transaction.
                # A retry with the same key returns this response without another debit.
                wallet = get_or_create_wallet(user.id, currency="KES")
                cost = int(app.config.get("DOC_CREDIT_COST", 1))
                wallet.spend_credits(cost, f"Document generation: {doc_type}", user=user)
            generation.status = "succeeded"
            generation.response_payload = result
            db.session.commit()
            return jsonify(result)

        except Exception:
            db.session.rollback()
            app.logger.exception("DocCraft generation failed")
            # Keep a saved request retryable after a provider or parsing failure.
            try:
                failed = GenerationRequest.query.filter_by(request_key=request_key).first()
                if failed is not None and failed.status != "succeeded":
                    failed.status = "failed"
                    db.session.commit()
            except SQLAlchemyError:
                db.session.rollback()
            return jsonify({"success": False, "error": "Generation failed. Please try again."}), 502

    return app


app = create_app()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "5000")))
