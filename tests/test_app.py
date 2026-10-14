from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_home():
    r = client.get("/")
    assert r.status_code == 200
    assert "Archivo TIC" in r.text

def test_health():
    assert client.get("/api/health").status_code == 200

def test_documents():
    r = client.get("/api/documents")
    assert r.status_code == 200
    assert isinstance(r.json()["documents"], list)

def test_question_validation():
    r = client.post("/api/ask", json={"question": "a"})
    assert r.status_code == 422

def test_sync_not_public():
    # FastAPI TestClient IP ficticia no loopback: bloqueado por diseño.
    r = client.post("/api/sync")
    assert r.status_code == 403
