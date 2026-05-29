"""HTTP /health route tests (plan §4.8 #5).

Uses Starlette TestClient against build_app(); monkeypatches health_check (the no-retry
behavior itself was proven in 2c). Verifies the route + 200/503 response shape."""
import pytest
from starlette.testclient import TestClient

import pr_agent.mosaico.server as server_mod
from pr_agent.mosaico.server import build_app


def _client(monkeypatch, health_value):
    async def fake_health_check():
        return health_value

    # health_check is imported into server_mod's namespace and called by _HealthApp._health.
    monkeypatch.setattr(server_mod, "health_check", fake_health_check)
    return TestClient(build_app())


class TestHealthRoute:
    def test_healthy_returns_200(self, monkeypatch):
        client = _client(monkeypatch, "OK")
        resp = client.get("/health")
        assert resp.status_code == 200
        body = resp.json()
        assert body["is_healthy"] is True
        assert body["status"] == "OK"

    def test_unhealthy_returns_503(self, monkeypatch):
        client = _client(monkeypatch, "Unhealthy: connection refused")
        resp = client.get("/health")
        assert resp.status_code == 503
        body = resp.json()
        assert body["is_healthy"] is False
        assert "Unhealthy" in body["status"]
        assert "Unhealthy" in body["detail"]
