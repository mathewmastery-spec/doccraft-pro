import os
import json
import ast
from pathlib import Path
from flask import Flask, render_template, request, jsonify
from openai import OpenAI

app = Flask(__name__)

source = Path("app_original_backup.py").read_text()
tree = ast.parse(source)
wanted = {"SYSTEM_PROMPTS", "REPLY_MESSAGES"}
found = {}

for node in tree.body:
    if isinstance(node, ast.Assign):
        for target in node.targets:
            if isinstance(target, ast.Name) and target.id in wanted:
                found[target.id] = ast.literal_eval(node.value)
    elif isinstance(node, ast.AnnAssign):
        if isinstance(node.target, ast.Name) and node.target.id in wanted:
            found[node.target.id] = ast.literal_eval(node.value)

SYSTEM_PROMPTS = found["SYSTEM_PROMPTS"]
REPLY_MESSAGES = found["REPLY_MESSAGES"]

@app.route("/")
def home():
    return render_template("doccraft.html")

@app.route("/health")
def health():
    return jsonify({"status": "ok", "app": "DocCraft"})

@app.route("/api/generate", methods=["POST"])
def generate():
    body = request.get_json(silent=True) or {}
    doc_type = body.get("doc_type", "resume")
    user_input = body.get("user_input", "")
    extra = body.get("extra") or {}

    if not isinstance(user_input, str) or not user_input.strip():
        return jsonify({"success": False, "error": "Please enter your information."}), 400

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return jsonify({"success": False, "error": "Generation is not configured yet."}), 503

    prompt = SYSTEM_PROMPTS.get(doc_type, SYSTEM_PROMPTS.get("resume", "Create a professional document and return valid JSON."))
    context = ""
    if isinstance(extra, dict) and extra.get("currentData"):
        context = "\n\nExisting data to merge with:\n" + json.dumps(extra["currentData"])

    try:
        client = OpenAI(api_key=api_key)
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": user_input + context}
            ],
            temperature=0.7,
            max_tokens=2000
        )
        raw = (response.choices[0].message.content or "").strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[-1]
            if raw.endswith("```"):
                raw = raw[:-3]
        data = json.loads(raw.strip())
        return jsonify({
            "success": True,
            "data": data,
            "reply": REPLY_MESSAGES.get(doc_type, "Document generated successfully!")
        })
    except Exception:
        app.logger.exception("DocCraft generation failed")
        return jsonify({"success": False, "error": "Generation failed. Please try again."}), 502

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "5000")))
