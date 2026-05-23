"""Error handler tests. JSON for /api/*, HTML otherwise."""

from __future__ import annotations


def test_api_404_returns_json_envelope(client):
    res = client.get("/api/v1/does-not-exist")
    assert res.status_code == 404
    assert res.is_json
    assert res.json["error"]["code"] == "NOT_FOUND"


def test_html_404_renders_page(client):
    res = client.get("/no-such-page")
    assert res.status_code == 404
    body = res.data.decode()
    assert "404" in body
    assert "/no-such-page" in body  # path is rendered into the page


def test_api_method_not_allowed(client):
    # POST to a GET-only endpoint → 405
    res = client.post("/api/v1/state")
    assert res.status_code == 405
    assert res.is_json
    assert res.json["error"]["code"] == "METHOD_NOT_ALLOWED"
