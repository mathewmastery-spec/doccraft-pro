def test_care_page_is_available(client):
    response = client.get("/care")
    assert response.status_code == 200
    assert b"DocCraft Care" in response.data
    assert b"What's on your mind?" in response.data


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
