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
