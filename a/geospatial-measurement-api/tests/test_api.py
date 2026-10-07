import json
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app
from app.repository import repository

client = TestClient(app)


def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_rejects_unsupported_extension():
    response = client.post("/api/files/", files={"file": ("sample.txt", b"hello", "text/plain")})
    assert response.status_code == 400


def test_missing_file_returns_404():
    response = client.get("/api/files/does-not-exist/")
    assert response.status_code == 404
