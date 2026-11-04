"""Regression checks for the front-end document style catalogue.

These are static integration guards, not a substitute for browser/print testing.
"""
from pathlib import Path
import re


TEMPLATE = Path(__file__).resolve().parents[1] / "templates" / "doccraft.html"
HTML = TEMPLATE.read_text(encoding="utf-8")

STYLE_IDS = (
    "classic", "modern", "minimal", "academic", "slate", "editorial",
    "technical", "sidebar", "correspondence", "institutional", "creative",
    "monochrome", "emerald", "burgundy", "bluebook",
)


def test_all_fifteen_styles_are_selectable():
    picker = re.search(r'<select id="templateSelect"[^>]*>(.*?)</select>', HTML, re.S)
    assert picker is not None
    options = re.findall(r'<option value="([^"]+)">', picker.group(1))
    assert options == list(STYLE_IDS)


def test_every_style_has_a_visual_skin():
    for style in STYLE_IDS:
        assert f'#docSheet[data-doc-style="{style}"]' in HTML


def test_style_switch_preserves_existing_wallet_authorization_for_resume():
    switch = HTML.split("async function setTemplate(tpl, picker) {", 1)[1].split(
        "\n}\n", 1
    )[0]
    assert "authorizeDocumentAction('template')" in switch
    assert "hasGeneratedDocument" in switch
    assert ".portfolio-sheet,.letter-sheet" in switch
    assert "state.template = tpl" in switch
    assert "picker.value = state.template" in switch


def test_resume_cv_layouts_support_extended_style_mapping():
    renderer = HTML.split("function renderResume(d) {", 1)[1].split(
        "\n}\n", 1
    )[0]
    assert "state.template === 'sidebar' ? 'modern'" in renderer
    assert "state.template === 'monochrome' ? 'minimal'" in renderer
    assert "renderClassic(d)" in renderer
    assert "renderModern(d)" in renderer
    assert "renderMinimal(d)" in renderer


def test_portfolio_and_both_letter_families_receive_selected_style():
    assert "function renderPortfolio(d) {\n  if (!d || !d.name) return;\n  applyDocumentStyle();" in HTML
    assert "function renderLetter(text, subject) {\n  if (!text) return;\n  applyDocumentStyle();" in HTML
    assert "function renderOrgLetter(text, subject) { renderLetter(text, subject || ''); }" in HTML


def test_generation_and_wallet_endpoints_remain_present():
    assert "fetch('/api/generate'" in HTML
    assert "fetch('/api/wallet/consume-action'" in HTML
    assert "fetch('/api/wallet/authorize-document'" in HTML


def test_more_tips_is_available_in_all_document_form_families():
    assert HTML.count("moreTipsMarkup()") == 6
    assert "More Tips to My Document" in HTML
    assert 'id="documentTips" maxlength="5000"' in HTML
    assert "additional_tips: readDocumentTips()" in HTML
    assert "extra: { documentTips: readDocumentTips() }" in HTML


def test_more_tips_are_included_in_local_document_previews_safely():
    assert "appendDocumentTipsToPreview(d.additional_tips)" in HTML
    assert 'paragraph.textContent = value;' in HTML
    assert 'heading.textContent = "Additional Information Supplied";' in HTML


def test_more_tips_are_validated_and_added_to_ai_generation_context():
    app_source = (TEMPLATE.parents[1] / "app.py").read_text(encoding="utf-8")
    assert 'extra.get("documentTips", "")' in app_source
    assert "len(document_tips) > 5000" in app_source
    assert "ADDITIONAL USER TIPS FOR THIS DOCUMENT" in app_source
    assert "Do not treat suggestions as verified facts" in app_source
    assert "do not invent missing information" in app_source