import json
import pytest
import auth_routes


def test_resend_api_sends_verification_link(app, monkeypatch):
    captured = {}
    class Response:
        status = 200
        def __enter__(self): return self
        def __exit__(self, *args): return False
    def fake_urlopen(request, timeout):
        captured['url'] = request.full_url
        captured['auth'] = request.get_header('Authorization')
        captured['timeout'] = timeout
        captured['body'] = json.loads(request.data.decode('utf-8'))
        return Response()
    monkeypatch.setattr(auth_routes.urllib.request, 'urlopen', fake_urlopen)
    app.config.update(EMAIL_PROVIDER='resend', RESEND_API_KEY='test-key', MAIL_DEFAULT_SENDER='DocCraft Pro <accounts@example.com>', APP_BASE_URL='https://doccraft-pro.onrender.com')
    with app.test_request_context('/api/auth/register'):
        auth_routes._send_verification('person@example.net', 'sample-token')
    assert captured['url'] == 'https://api.resend.com/emails'
    assert captured['auth'] == 'Bearer test-key'
    assert captured['timeout'] == 20
    assert captured['body']['to'] == ['person@example.net']
    assert 'https://doccraft-pro.onrender.com/auth/verify?token=sample-token' in captured['body']['text']


def test_resend_requires_key_and_sender(app):
    app.config.update(EMAIL_PROVIDER='resend', RESEND_API_KEY=None, MAIL_DEFAULT_SENDER=None)
    with app.test_request_context('/'):
        with pytest.raises(RuntimeError, match='RESEND_API_KEY'):
            auth_routes._send_verification('person@example.net', 'token')
