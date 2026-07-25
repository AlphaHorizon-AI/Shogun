from __future__ import annotations

import logging

from fastapi.testclient import TestClient

from gensui.app import create_app
from gensui.config import gensui_settings


def _frontend(tmp_path):
    dist = tmp_path / "dist"
    assets = dist / "assets"
    assets.mkdir(parents=True)
    (dist / "index.html").write_text("<title>Gensui — Central Command</title>", encoding="utf-8")
    (assets / "app.js").write_text("const api = '/api/gensui';", encoding="utf-8")
    return dist


def test_gensui_serves_root_assets_spa_and_api_without_route_collision(
    tmp_path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(gensui_settings, "gensui_frontend_dist", _frontend(tmp_path))
    client = TestClient(create_app())
    try:
        root = client.get("/")
        asset = client.get("/assets/app.js")
        spa = client.get("/agents")
        health = client.get("/api/gensui/health")
        missing_api = client.get("/api/gensui/not-a-route")
    finally:
        client.close()

    assert root.status_code == 200
    assert "Gensui" in root.text
    assert asset.status_code == 200
    assert "/api/gensui" in asset.text
    assert spa.status_code == 200
    assert "Gensui" in spa.text
    assert health.status_code == 200
    assert health.json()["service"] == "gensui"
    assert missing_api.status_code == 404
    assert missing_api.headers["content-type"].startswith("application/json")


def test_missing_gensui_frontend_is_visible_in_logs(
    tmp_path,
    monkeypatch,
    caplog,
) -> None:
    missing = tmp_path / "missing"
    monkeypatch.setattr(gensui_settings, "gensui_frontend_dist", missing)
    with caplog.at_level(logging.WARNING, logger="gensui"):
        app = create_app()
    assert any(str(missing) in record.message for record in caplog.records)
    client = TestClient(app)
    try:
        assert client.get("/").status_code == 404
    finally:
        client.close()
