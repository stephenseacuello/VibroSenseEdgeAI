"""Health-probe tests."""

from __future__ import annotations


def test_healthz_ok(client):
    res = client.get("/healthz")
    assert res.status_code == 200
    assert res.json["status"] == "ok"
    assert "version" in res.json


def test_readyz_ok_when_db_exists(client):
    res = client.get("/readyz")
    assert res.status_code == 200
    assert res.json["status"] == "ready"


def test_readyz_503_when_db_missing(tmp_path, monkeypatch):
    # Point at a directory that exists but a file that doesn't; sqlite will create it,
    # so instead point at a directory path which sqlite cannot open for SELECT.
    bad = tmp_path / "nonexistent" / "missing.sqlite"
    monkeypatch.setenv("VIBROSENSE_DB", str(bad))
    monkeypatch.setenv("VIBROSENSE_NO_BRIDGE", "1")
    from app import create_app

    a = create_app()
    a.config["TESTING"] = True
    res = a.test_client().get("/readyz")
    assert res.status_code == 503
    assert res.json["status"] == "not-ready"
