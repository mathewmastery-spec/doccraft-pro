import os
import json
import ast
from pathlib import Path
from flask import Flask, render_template, request, jsonify, Response
from openai import OpenAI

app = Flask(__name__)

SYSTEM_PROMPTS = {'resume': 'You are an expert resume writer. Parse the user\'s input and return a JSON object with these fields:\n{\n  "name": "", "email": "", "phone": "", "location": "", "linkedin": "", "website": "",\n  "summary": "",\n  "skills": ["skill1", "skill2"],\n  "languages": ["English (Fluent)"],\n  "certifications": ["cert1"],\n  "experience": [{"title":"","company":"","period":"","location":"","bullets":["achievement1"]}],\n  "education": [{"degree":"","institution":"","year":"","grade":""}],\n  "projects": [{"name":"","description":"","tech":["tech1"]}]\n}\nMerge with any existing data. Make the summary compelling and professional. Expand bullet points into strong action-verb statements. Return ONLY the JSON object, no extra text.', 'cv': 'You are an expert CV writer for academic and professional positions. Parse the user\'s input and return a JSON object with these fields:\n{\n  "name": "", "email": "", "phone": "", "location": "", "linkedin": "", "website": "",\n  "summary": "",\n  "skills": ["skill1"],\n  "languages": ["English (Fluent)"],\n  "certifications": [],\n  "experience": [{"title":"","company":"","period":"","location":"","bullets":[]}],\n  "education": [{"degree":"","institution":"","year":"","grade":""}],\n  "projects": [{"name":"","description":"","tech":[]}]\n}\nCVs are more detailed than resumes. Include all relevant academic and professional experience. Return ONLY the JSON object.', 'academic_cv': 'You are an expert academic CV writer. Parse the user\'s input and return a JSON object with these fields:\n{\n  "name": "", "email": "", "phone": "", "location": "", "linkedin": "", "website": "",\n  "summary": "",\n  "skills": [],\n  "languages": [],\n  "certifications": [],\n  "experience": [{"title":"","company":"","period":"","location":"","bullets":[]}],\n  "education": [{"degree":"","institution":"","year":"","grade":""}],\n  "projects": [{"name":"","description":"","tech":[]}]\n}\nEmphasise research, publications, academic achievements and scholarly work. Return ONLY the JSON object.', 'cover_letter': 'You are an expert cover letter writer. Based on the user\'s details, write a compelling, professional cover letter.\nReturn a JSON object:\n{\n  "full_letter": "Dear [Hiring Manager],\\n\\n[Opening paragraph]\\n\\n[Body paragraph 1]\\n\\n[Body paragraph 2]\\n\\nYours sincerely,\\n[Name]",\n  "subject": "Application for [Position] – [Name]"\n}\nThe letter should be warm, confident, and tailored. 3-4 paragraphs. Return ONLY the JSON object.', 'portfolio': 'You are an expert portfolio document writer. Parse the user\'s input and return a JSON object:\n{\n  "name": "", "title": "", "bio": "",\n  "contact": {"email": "", "github": "", "linkedin": ""},\n  "skills": [{"name": "React", "level": 90}],\n  "projects": [{"name":"","description":"","tech":[]}],\n  "education": [{"degree":"","institution":"","year":""}],\n  "achievements": ["achievement1"]\n}\nMake the bio compelling and the descriptions impactful. Return ONLY the JSON object.', 'org_letter': 'You are an expert formal letter writer. Based on the details provided, write a professional formal letter.\nReturn a JSON object:\n{\n  "letter_text": "Full formal letter text here with proper salutation, body paragraphs, and sign-off"\n}\nUse proper formal letter formatting with today\'s date, addresses, salutation, 3-4 body paragraphs, and sign-off. Return ONLY the JSON object.'}
REPLY_MESSAGES = {'resume': 'Your resume has been generated! You can see it in the preview. Switch templates or edit the form to refine it.', 'cv': 'Your CV is ready in the preview panel. Feel free to ask me to add more sections or details.', 'academic_cv': "Your Academic CV has been created. I've emphasised your academic achievements and research.", 'cover_letter': "Your cover letter is ready in the preview. It's tailored and professional.", 'portfolio': 'Your portfolio document is ready! It showcases your work beautifully.', 'org_letter': 'Your formal letter has been generated and is ready in the preview.'}

@app.route("/")
def home():
    return render_template("doccraft.html")
@app.route("/robots.txt")
def robots_txt():
    content = """User-agent: *
Allow: /
Disallow: /api/
Disallow: /health

Sitemap: https://doccraft-pro.onrender.com/sitemap.xml
"""
    return Response(content, mimetype="text/plain")


@app.route("/sitemap.xml")
def sitemap_xml():
    content = """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url>
    <loc>https://doccraft-pro.onrender.com/</loc>
  </url>
</urlset>
"""
    return Response(content, mimetype="application/xml")
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
             max_tokens=2000,
response_format={"type": "json_object"}
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
