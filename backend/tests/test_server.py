from fastapi.testclient import TestClient
import pytest
from server import app

client = TestClient(app)

def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

def test_chat_invalid_payload():
    response = client.post("/chat", json={"invalid": "field"})
    assert response.status_code == 422 # Marshalling error

def test_chat_empty_text():
    response = client.post("/chat", json={"text": ""})
    assert response.status_code == 400
    assert response.json()["detail"] == "Text cannot be empty"

# Note: We won't test full graph invocation in a unit test 
# as it requires LLM keys, but we verified the health and basic validation.
