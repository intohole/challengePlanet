from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.probe import register_probe

VALID_STATUS: set[str] = {"ok", "fail", "degraded", "unknown", "skipped"}
CHECK_KEYS: list[str] = ["llm", "db", "notify", "scheduler", "watermark"]


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("SERVICE_TOKEN", "probe-test-token")
    app: FastAPI = FastAPI()
    register_probe(app)
    return TestClient(app)


def test_probe_anonymous_denied(client: TestClient) -> None:
    assert client.get("/api/_internal/probe").status_code == 401


def test_probe_wrong_token_denied(client: TestClient) -> None:
    resp = client.get("/api/_internal/probe", headers={"X-Service-Token": "wrong"})
    assert resp.status_code == 401


def test_probe_valid_token_contract(client: TestClient) -> None:
    resp = client.get(
        "/api/_internal/probe", headers={"X-Service-Token": "probe-test-token"}, params={"fresh": 1}
    )
    assert resp.status_code == 200
    body: dict[str, object] = resp.json()
    assert body["schema"] == 2
    assert body["app"] == "challengePlanet"
    assert body["overall"] in VALID_STATUS
    checks: dict[str, object] = body["checks"]
    for key in CHECK_KEYS:
        assert key in checks
        assert checks[key]["status"] in VALID_STATUS
        assert "detail" in checks[key]
        assert "evidence" in checks[key]
