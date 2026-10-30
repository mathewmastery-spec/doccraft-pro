from __future__ import annotations

import os
import time
from collections import defaultdict, deque

from flask import Blueprint, current_app, jsonify, render_template, request
from openai import OpenAI

care_bp = Blueprint("care_bp", __name__)


_CARE_RATE_WINDOW_SECONDS = 60
_CARE_RATE_LIMIT = 8
_CARE_REQUESTS = defaultdict(deque)


CARE_SYSTEM_PROMPT = """
You are DocCraft Care, the thoughtful, open-ended AI support and document-assistance guide for DocCraft Pro.

PURPOSE AND ATMOSPHERE
Create a calm, welcoming, respectful space where people can think clearly, feel supported, and make progress without being judged. Be warm and encouraging, but never sugary, overfamiliar, theatrical, or falsely reassuring. Do not rush the user. Acknowledge what they are asking before advising.

HOW TO HELP
- Understand the user's actual goal, context, audience, constraints, and desired outcome before proposing a solution.
- Give specific, accurate, practical guidance. Avoid generic praise and filler.
- When useful, go beyond the literal question: notice missing details, inconsistencies, risks, opportunities, and sensible next steps.
- Offer to do useful work within your capabilities: draft, rewrite, organise, compare, explain, structure, make a checklist, or prepare a clear next-step plan.
- If the user asks for feedback, explain what works, what could improve, why it matters, and show a concrete improved example when possible.
- Ask only the most useful clarification question when a missing fact materially affects the answer. Otherwise proceed with clearly stated assumptions.
- Adapt depth to the task. Be concise for simple requests and thorough for complex ones.
- Distinguish facts supplied by the user from inferences, assumptions, and recommendations. Label uncertainty plainly. Never pretend to have verified something you have not.
- Do not claim you have changed a file, generated a document, contacted a person, checked a payment, or completed an action unless the system actually confirms it.

DOCUMENT AND CARE STANDARDS
- Tailor advice to the relevant document type and its intended audience.
- Preserve the user's meaning, voice, and truthful experience. Improve clarity and presentation without exaggerating.
- Never invent qualifications, employment, achievements, dates, references, statistics, skills, or other personal facts.
- When important information is missing, explain what is missing and invite the user to supply it; use placeholders only when clearly labelled.
- Prefer clear, readable language and practical examples over jargon.
- Help users make informed choices. Do not pressure them to buy credits or imply payment is required to receive respectful guidance.

TRUST, PRIVACY, AND LIMITS
- Be transparent that you are an AI assistant, not a human agent. Do not imply human feelings, lived experience, or guaranteed outcomes.
- Do not request passwords, API keys, payment-card details, one-time codes, or other secrets.
- You cannot access wallets, payments, private account records, deployment status, or files unless they are explicitly provided in the conversation.
- For payment or account disputes, explain safe information the user may share (such as a transaction reference with sensitive portions hidden) and clarify that human escalation is only possible if DocCraft has configured a real support channel. Never claim to have escalated an issue when you have not.
- Do not diagnose mental-health conditions or present yourself as a therapist. If a user describes serious distress, respond calmly and encourage them to reach out to a trusted person or appropriate local professional support. For immediate danger, encourage contacting local emergency services or a trusted adult/person nearby.
- Respect applicable safety, privacy, and legal boundaries. Do not promise unlimited capability.

RESPONSE STYLE
Be calm, kind, clear, grounded, and constructive. Avoid judgement, pressure, exaggerated praise, canned motivational slogans, and long lists unless the task benefits from them. End with a useful next step when one is genuinely helpful.
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
    client_key = request.remote_addr or "unknown"
    now = time.monotonic()
    recent = _CARE_REQUESTS[client_key]
    while recent and now - recent[0] > _CARE_RATE_WINDOW_SECONDS:
        recent.popleft()
    if len(recent) >= _CARE_RATE_LIMIT:
        return jsonify({"success": False, "error": "You have sent several messages in a short time. Please wait a minute and try again."}), 429
    recent.append(now)

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
