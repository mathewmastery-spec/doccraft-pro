from __future__ import annotations

import os

from flask import Flask, Response, jsonify, render_template, request
from openai import OpenAI

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


def create_app(test_config=None):
    app = Flask(__name__)
    app.config.from_object(config)
    if test_config:
        app.config.update(test_config)

    db.init_app(app)
    migrate.init_app(app, db)
    app.register_blueprint(billing_bp)

    @app.route("/")
    def home():
        return render_template("doccraft.html")

    @app.route("/robots.txt")
    def robots_txt():
        return Response("""User-agent: *\nAllow: /\nDisallow: /api/\nDisallow: /health\n\nSitemap: https://doccraft-pro.onrender.com/sitemap.xml\n""", mimetype="text/plain")

    @app.route("/sitemap.xml")
    def sitemap_xml():
        return Response("""<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n<urlset xmlns=\"http://www.sitemaps.org/schemas/sitemap/0.9\">\n  <url>\n    <loc>https://doccraft-pro.onrender.com/</loc>\n  </url>\n</urlset>\n""", mimetype="application/xml")

    @app.route("/health")
    def health():
        return jsonify({"status": "ok", "app": "DocCraft"})

    @app.route("/api/generate", methods=["POST"])
    def generate():
        payload = request.get_json(silent=True) or {}
        doc_type = payload.get("doc_type", "resume")
        user_input = payload.get("user_input", "")
        extra = payload.get("extra") or {}
        request_key = payload.get("request_id") or payload.get("idempotency_key") or None

        if not isinstance(user_input, str) or not user_input.strip():
            return jsonify({"success": False, "error": "Please enter your information."}), 400

        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            return jsonify({"success": False, "error": "Generation is not configured yet."}), 503

        email = (payload.get("email") or payload.get("user_email") or "").strip().lower()
        user = None
        if email:
            from models import ensure_user, get_or_create_wallet
            user = ensure_user(email, full_name=payload.get("full_name"), country_code=payload.get("country_code") or "KE")
            wallet = get_or_create_wallet(user.id, currency="KES")
            if app.config.get("BILLING_ENABLED", False):
                cost = int(app.config.get("DOC_CREDIT_COST", 1))
                if wallet.balance_credits < cost:
                    return jsonify({"success": False, "error": "Insufficient wallet credits. Purchase a credit package or wait for a free grant.", "wallet_balance": wallet.balance_credits}), 402

        prompt = SYSTEM_PROMPTS.get(doc_type, SYSTEM_PROMPTS.get("resume", "Create a professional document and return valid JSON."))
        context = ""
        if isinstance(extra, dict) and extra.get("currentData"):
            context = "\n\nExisting data to merge with:\n" + __import__("json").dumps(extra["currentData"])

        try:
            client = OpenAI(api_key=api_key)
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": user_input + context},
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
            data = __import__("json").loads(raw.strip())
            result = {"success": True, "data": data, "reply": REPLY_MESSAGES.get(doc_type, "Document generated successfully!")}
            if email and app.config.get("BILLING_ENABLED", False):
                from models import get_or_create_wallet
                wallet = get_or_create_wallet(user.id, currency="KES")
                wallet.spend_credits(int(app.config.get("DOC_CREDIT_COST", 1)), f"Document generation: {doc_type}", user=user)
                db.session.commit()
            return jsonify(result)
        except Exception:
            app.logger.exception("DocCraft generation failed")
            return jsonify({"success": False, "error": "Generation failed. Please try again."}), 502

    return app


app = create_app()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "5000")))
