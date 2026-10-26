# DocCraft Pro — Professional Document Design System

## Goal
Build a production-grade document design library with at least 12 distinct, print-ready styles, available consistently across all six supported document types and both generation paths (structured forms and corporate AI chat).

## Non-negotiable scope protection
- Work only on document rendering, template selection, and document-specific print/PDF styling.
- Do not alter wallet authorization/deductions, payment providers, billing endpoints, generation APIs/prompts, authentication, database models, analytics, PWA behavior, or unrelated page layout.
- Keep changes on `feature/professional-document-design-system` until implementation and regression checks pass.
- Preserve the mobile auto-preview behavior already merged to main.

## Six document types
1. Resume
2. CV
3. Academic CV
4. Cover Letter
5. Portfolio
6. Organizational Letter

The design selector must apply regardless of whether content came from form submission or corporate AI chat. It must not regenerate content or trigger a second credit action merely because a user changes visual style.

## Initial style catalogue (12)
1. **Classic Executive** — restrained serif headings, formal hierarchy, black/charcoal ink.
2. **Modern Corporate** — navy accents, contemporary type, strong hierarchy.
3. **Minimal ATS** — single column, semantic headings, no decorative layout, parser-friendly.
4. **Academic Scholar** — publication-oriented hierarchy, credentials, research and teaching emphasis.
5. **Professional Slate** — neutral slate palette, balanced spacing, versatile business style.
6. **Elegant Editorial** — refined serif display typography, fine rules, generous whitespace.
7. **Technical Grid** — structured skills/projects, precise alignment, restrained technical accents.
8. **Contemporary Sidebar** — compact supporting rail where suitable; single-column fallback for letters and ATS needs.
9. **Formal Correspondence** — conventional letter spacing, date/recipient/subject/sign-off hierarchy.
10. **Institutional** — conservative, official-document presentation, restrained rules and no ornamental graphics.
11. **Creative Portfolio** — expressive but print-safe section headers and project presentation.
12. **Clean Monochrome** — strong black-and-white contrast, consistent typography, no color dependence.

Styles must be adapted to the document type rather than forcing identical layouts on every document. For example, cover letters and organizational letters should retain formal letter structure; academic CVs should support long multi-page content; portfolios may use richer project blocks; resumes should keep a sensible ATS-friendly option.

## Production requirements
- Print/PDF output must match the on-screen document, not the surrounding application UI.
- Use a print stylesheet with white page backgrounds, controlled ink colors, stable margins, hidden controls, and explicit page-break rules.
- Avoid clipped content, overlapping columns, orphaned headings, split contact details, and accidental blank pages.
- Do not rely on color alone to communicate meaning; ensure grayscale printing remains legible.
- Use semantic headings and readable type sizes; preserve text selection and copying.
- Long CVs, academic CVs, and portfolios must flow across pages rather than being forced into a fixed-height sheet.
- Responsive mobile preview must remain readable without changing the intended print layout.
- Keep existing free-preview watermark behavior intact.
- Style changes must not consume document-generation credits; any existing intended template-action billing must be reviewed and preserved rather than silently changed.

## Implementation sequence
1. Map all current renderers and generation entry points; record the CSS classes and data fields each document type uses.
2. Introduce a central style catalogue and stable style identifiers without changing content generation or billing.
3. Refactor rendering so the selected style is applied consistently to form-generated and AI-generated output for all six document types.
4. Implement the 12 styles as document-aware variants with print-safe and mobile-safe adaptations.
5. Improve print/PDF pagination and remove app-only controls from output.
6. Add/extend automated checks for style selection, six document types, long content, missing optional fields, print rules, and credit-action isolation.
7. Manually verify representative documents on desktop and mobile, including actual print/save-as-PDF output.
8. Open a pull request for review. Do not merge or deploy until regression checks pass.

## Acceptance checklist
- [ ] At least 12 clearly distinct styles appear in the style selector.
- [ ] Every style works for all six document types.
- [ ] Form and AI-chat paths produce the same style quality for equivalent content.
- [ ] Changing a style does not regenerate document content.
- [ ] No unintended wallet action or extra credit deduction is introduced.
- [ ] Preview, copy, and print/download behavior remains intact.
- [ ] Multi-page documents print without clipped content or forced one-page compression.
- [ ] Existing mobile auto-preview behavior remains intact.
- [ ] Billing, payments, generation API, and unrelated UI files remain unchanged.
- [ ] Regression checks pass before merge and deployment.
