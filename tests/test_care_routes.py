def test_care_is_embedded_in_main_workspace(client):
    response = client.get("/")
    assert response.status_code == 200
    assert b"Need more help?" in response.data
    assert b'id="carePopupBackdrop"' in response.data
    assert b'id="careOpen"' in response.data
    assert b'role="dialog"' in response.data


def test_care_has_no_standalone_page(client):
    response = client.get("/care")
    assert response.status_code == 404


def test_care_rejects_empty_message(client):
    response = client.post("/api/care/chat", json={"message": "   "})
    assert response.status_code == 400
    assert response.get_json()["success"] is False


def test_care_rejects_oversized_message(client):
    response = client.post("/api/care/chat", json={"message": "x" * 5001})
    assert response.status_code == 413


def test_care_rejects_invalid_history(client):
    response = client.post(
        "/api/care/chat",
        json={"message": "Can you help?", "history": "not-a-list"},
    )
    assert response.status_code == 400


def test_care_returns_ai_reply_without_wallet_dependency(client, app, monkeypatch):
    from types import SimpleNamespace
    import care_routes

    class FakeCompletions:
        @staticmethod
        def create(**kwargs):
            assert kwargs["messages"][-1]["content"] == "Please help me organise my experience."
            return SimpleNamespace(
                choices=[SimpleNamespace(message=SimpleNamespace(content="Let's organise it step by step."))]
            )

    class FakeOpenAI:
        def __init__(self, **kwargs):
            self.chat = SimpleNamespace(completions=FakeCompletions())

    monkeypatch.setattr(care_routes, "OpenAI", FakeOpenAI)
    app.config.update({"AI_PROVIDER": "openai", "OPENAI_API_KEY": "test-key"})

    response = client.post(
        "/api/care/chat",
        json={"message": "Please help me organise my experience.", "history": [], "context": {}},
    )

    assert response.status_code == 200
    assert response.get_json() == {
        "success": True,
        "reply": "Let's organise it step by step.",
    }


def test_career_mode_switch_is_home_level_and_preserves_document_studio(client):
    response = client.get("/")
    assert response.status_code == 200
    page = response.data
    assert b'class="nav-workspaces"' in page
    assert b'data-mode-choice="documents"' in page
    assert b'data-mode-choice="career"' in page
    assert b'>Document Studio</b>' in page
    assert b'>Smart Potential Lab</b>' in page
    assert b'id="documentStudioHome"' in page
    assert b'id="careerLaunchHome"' in page
    assert b'id="appScreen"' in page
    assert b"function switchProductMode(mode)" in page
    assert b"function startCareerResume()" in page
    assert b"function startCareerCoverLetter()" in page
    assert b"career_opportunity" in page


def test_career_opportunity_context_is_bounded_and_not_applicant_fact(client, app, monkeypatch):
    from types import SimpleNamespace
    import care_routes

    captured = {}

    class FakeCompletions:
        @staticmethod
        def create(**kwargs):
            captured["messages"] = kwargs["messages"]
            return SimpleNamespace(
                choices=[SimpleNamespace(message=SimpleNamespace(content="Please tell me which requirements match your actual experience."))]
            )

    class FakeOpenAI:
        def __init__(self, **kwargs):
            self.chat = SimpleNamespace(completions=FakeCompletions())

    monkeypatch.setattr(care_routes, "OpenAI", FakeOpenAI)
    app.config.update({"AI_PROVIDER": "openai", "OPENAI_API_KEY": "test-key"})
    response = client.post(
        "/api/care/chat",
        json={
            "message": "Help me compare my experience.",
            "history": [],
            "context": {
                "document_type": "resume",
                "career_opportunity": {
                    "opportunityType": "job",
                    "role": "Network Technician",
                    "organisation": "Example Ltd",
                    "description": "Requires TCP/IP and fibre experience.",
                },
            },
        },
    )
    assert response.status_code == 200
    prompt = captured["messages"][0]["content"]
    assert "Network Technician" in prompt
    assert "Example Ltd" in prompt
    assert "not evidence" in prompt
    assert "Never" in prompt
