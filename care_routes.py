from __future__ import annotations

import os

from flask import Blueprint, current_app, jsonify, render_template, request
from openai import OpenAI

care_bp = Blueprint("care_bp", __name__)


CARE_SYSTEM_PROMPT = """
You are DocCraft Care, the open-ended AI customer-support and document-assistance guide for DocCraft Pro.
Be calm, respectful, practical, emotionally considerate, and concise. Help users with document questions,
unusual requirements, ideas, form fields, writing improvements, and basic DocCraft navigation.
Treat the user's needs as more important than completing a sale. Never pressure users to buy credits,
never use emotional vulnerability to sell, and never imply that a purchase is necessary to receive respect.
Be transparent that you are an AI assistant, not a human support agent. Do not claim to have checked a
wallet, payment, account, deployment, or private record. You cannot access those records.
Do not request passwords, API keys, payment card details, one-time codes, or other secrets. For payment
or account disputes, explain what information the user can safely share (for example, transaction
reference with sensitive portions hidden) and say that a human support route must be configured by
DocCraft before you can hand the issue to a person.
Ask focused clarification questions when needed. Offer suggestions as suggestions, not facts.
Never invent a user's qualifications, employment, achievements, dates, or other personal facts.
When helping with documents, preserve the user's meaning and ask before adding unverified claims.
If a user sounds frustrated, acknowledge the difficulty without overdoing sympathy, then offer a clear
next step. Do not diagnose emotions or mental-health conditions.
Do not claim unrestricted ability: follow applicable safety, privacy, and legal boundaries.
""".strip()


def _provider_config():
    provider = str(current_app.config.get("AI_PROVIDER") or os.getenv("AI_PROVIDER") or "openai").strip().lower()
    if provider == "gemini":
        key = current_app.config.get("GEMINI_API_KEY") or os.getenv("GEMINI_API_KEY")
        model = current_app.config.get("GEMINI_MODEL") or os.getenv("GEMINI_MODEL") or "gemini-3.8-flash"
    elif provider == "grok":
        key = current_app.config.get("GROK_API_KEY") or os.getenv("GROK_API_KEY") or os.getenv("XAI_API_KEY")
        model = current_app.config.get("GROK_MODEL") or os.getenv("GROK_MODEL") or "grok-4.7"
    elif provider == "groq":
        key = current_app.config.get("GROQ_API_KEY") or os.getenv("GROQ_API_KEY")
        model = current_app.config.get("GROQ_MODEL") or os.getenv("GROQ_MODEL") or "openai/gpt-oss-120b"
    elif provider == "openai":
        key = current_app.config.get("OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY")
        model = "gpt-4o-mini"
    else:
        raise ValueError("The configured AI provider is not supported.")
    return provider, key, model


@care_bp.get("/care")
def care_page():
    response = current_app.make_response(render_template("doccraft_care.html"))
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response


@care_bp.post("/api/care/chat")
def care_chat():
    payload = request.get_json(silent=True) or {}
    if not isinstance(payload, dict):
        return jsonify({"success": False, "error": "Please send a valid message."}), 400

    message = payload.get("message")
    if not isinstance(message, str) or not message.strip():
        return jsonify({"success": False, "error": "Write a message so DocCraft Care can help."}), 400
    if len(message) > 5000:
        return jsonify({"success": False, "error": "Please keep each message under 5,000 characters."}), 413

    history = payload.get("history") or []
    if not isinstance(history, list):
        return jsonify({"success": False, "error": "The conversation could not be read. Please start a new message."}), 400
    safe_history = []
    for item in history[-10:]:
        if not isinstance(item, dict):
            continue
        role = item.get("role")
        content = item.get("content")
        if role in {"user", "assistant"} and isinstance(content, str) and content.strip():
            safe_history.append({"role": role, "content": content[:3000]})

    context = payload.get("context") or {}
    if not isinstance(context, dict):
        context = {}
    doc_type = str(context.get("document_type") or "")[:80]
    name = str(context.get("display_name") or "").strip()[:80]
    context_note = ""
    if doc_type:
        context_note += "\nCurrent document area: " + doc_type
    if name:
        context_note += "\nThe user supplied this preferred name for this conversation: " + name

    try:
        provider, api_key, model = _provider_config()
        if not api_key:
            return jsonify({"success": False, "error": "DocCraft Care is temporarily unavailable because the AI service is not configured. Please try again later."}), 503

        if provider == "gemini":
            from google import genai
            from google.genai import types

            client = genai.Client(
                api_key=api_key,
                http_options=types.HttpOptions(timeout=45000, retry_options=types.HttpRetryOptions(attempts=1)),
            )
            contents = []
            for item in safe_history:
                contents.append(types.Content(
                    role="user" if item["role"] == "user" else "model",
                    parts=[types.Part.from_text(text=item["content"])],
                ))
            contents.append(types.Content(role="user", parts=[types.Part.from_text(text=message.strip() + context_note)]))
            result = client.models.generate_content(
                model=model,
                contents=contents,
                config=types.GenerateContentConfig(
                    system_instruction=CARE_SYSTEM_PROMPT,
                    temperature=0.6,
                    max_output_tokens=1200,
                ),
            )
            answer = (result.text or "").strip()
        else:
            if provider == "grok":
                client = OpenAI(api_key=api_key, base_url="https://api.x.ai/v1")
            elif provider == "groq":
                client = OpenAI(api_key=api_key, base_url="https://api.groq.com/openai/v1")
            else:
                client = OpenAI(api_key=api_key)

            messages = [{"role": "system", "content": CARE_SYSTEM_PROMPT + context_note}]
            messages.extend(safe_history)
            messages.append({"role": "user", "content": message.strip()})
            completion_args = {
                "model": model,
                "messages": messages,
                "max_tokens": 1200,
                "temperature": 0.6,
            }
            if provider == "groq" and model.startswith("openai/gpt-oss"):
                completion_args.pop("max_tokens", None)
                completion_args["max_completion_tokens"] = 1200
                completion_args["reasoning_effort"] = "low"
                completion_args["temperature"] = 1
            result = client.chat.completions.create(**completion_args)
            answer = (result.choices[0].message.content or "").strip()

        if not answer:
            return jsonify({"success": False, "error": "I couldn't prepare a useful reply just now. Please try rephrasing your message."}), 502
        return jsonify({"success": True, "reply": answer})
    except ValueError as exc:
        current_app.logger.warning("DocCraft Care configuration issue: %s", exc)
        return jsonify({"success": False, "error": "DocCraft Care is not configured for the selected AI provider."}), 503
    except Exception:
        current_app.logger.exception("DocCraft Care request failed")
        return jsonify({"success": False, "error": "DocCraft Care could not reach the AI service. Your message was not charged from your DocCraft wallet. Please try again shortly."}), 502
