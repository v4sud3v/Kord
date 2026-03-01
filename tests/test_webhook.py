from fastapi.testclient import TestClient

from main import app
from app.routes.webhook import handle_incoming_message

client = TestClient(app)

# --- unit test: handler function ---

def test_handle_incoming_message_returns_ok(capsys):
    result = handle_incoming_message(body="Hey", from_number="whatsapp:+9999999999")
    assert result == {"status": "ok"}
    captured = capsys.readouterr()
    assert "whatsapp:+9999999999" in captured.out
    assert "Hey" in captured.out


# --- integration test: route ---

def test_webhook_route_returns_ok():
    response = client.post(
        "/webhook",
        data={"Body": "Hello", "From": "whatsapp:+9999999999"},
    )
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_webhook_route_missing_fields():
    response = client.post("/webhook", data={})
    assert response.status_code == 422

