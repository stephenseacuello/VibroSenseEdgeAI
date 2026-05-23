"""REST API tests. See PROJECT_PLAN.md §13.2 / §14.4."""

from __future__ import annotations


# /api/v1/state -------------------------------------------------------------

def test_state_latest_for_default_asset(client):
    res = client.get("/api/v1/state")
    assert res.status_code == 200
    assert res.json["state"] == "HEALTHY"
    assert res.json["asset_id"] == "fan-01"
    assert res.json["seq"] == 3


def test_state_filter_by_asset(client):
    res = client.get("/api/v1/state?asset_id=fan-02")
    assert res.status_code == 200
    assert res.json["state"] == "BEARING_FAULT"


def test_state_404_for_unknown_asset(client):
    res = client.get("/api/v1/state?asset_id=does-not-exist")
    assert res.status_code == 404
    assert res.json["error"]["code"] == "NO_DATA"


# /api/v1/history -----------------------------------------------------------

def test_history_bad_range_missing(client):
    res = client.get("/api/v1/history")
    assert res.status_code == 400
    assert res.json["error"]["code"] == "BAD_RANGE"


def test_history_bad_range_not_iso(client):
    res = client.get("/api/v1/history?from=yesterday&to=today")
    assert res.status_code == 400
    assert res.json["error"]["code"] == "BAD_RANGE"


def test_history_returns_rows(client):
    res = client.get(
        "/api/v1/history?from=2026-07-15T14:29:00Z&to=2026-07-15T14:31:00Z"
    )
    assert res.status_code == 200
    rows = res.json
    assert len(rows) == 3
    assert [r["state"] for r in rows] == ["HEALTHY", "IMBALANCE", "HEALTHY"]


# /api/v1/oee ---------------------------------------------------------------

def test_oee_returns_availability(client):
    res = client.get("/api/v1/oee?window=99999999")
    assert res.status_code == 200
    body = res.json
    assert body["samples"] == 3
    # 2 of 3 HEALTHY for fan-01
    assert abs(body["availability"] - 2 / 3) < 1e-9


def test_oee_rejects_non_positive_window(client):
    res = client.get("/api/v1/oee?window=0")
    assert res.status_code == 400
    assert res.json["error"]["code"] == "BAD_PARAM"


def test_oee_rejects_bad_int(client):
    res = client.get("/api/v1/oee?window=banana")
    assert res.status_code == 400
    assert res.json["error"]["code"] == "BAD_PARAM"


def test_oee_empty_window(client):
    # asset with no recent rows → samples=0, availability=None
    res = client.get("/api/v1/oee?asset_id=does-not-exist&window=60")
    assert res.status_code == 200
    assert res.json["samples"] == 0
    assert res.json["availability"] is None


# /api/v1/assets ------------------------------------------------------------

def test_assets_lists_known(client):
    res = client.get("/api/v1/assets")
    assert res.status_code == 200
    ids = [r["asset_id"] for r in res.json]
    assert ids == ["fan-01", "fan-02"]


# /api/v1/alarms ------------------------------------------------------------

def test_alarms_returns_recent_first(client):
    res = client.get("/api/v1/alarms")
    assert res.status_code == 200
    rows = res.json
    assert len(rows) == 2  # only fan-01 seeded alarms
    # newest first
    assert rows[0]["from_state"] == "IMBALANCE"
    assert rows[0]["to_state"] == "HEALTHY"
    assert rows[1]["from_state"] == "HEALTHY"
    assert rows[1]["to_state"] == "IMBALANCE"


def test_alarms_filter_by_asset(client):
    res = client.get("/api/v1/alarms?asset_id=fan-02")
    assert res.status_code == 200
    rows = res.json
    assert len(rows) == 1
    # the first transition can have a NULL from_state
    assert rows[0]["from_state"] is None
    assert rows[0]["to_state"] == "BEARING_FAULT"


def test_alarms_empty_for_unknown_asset(client):
    res = client.get("/api/v1/alarms?asset_id=does-not-exist")
    assert res.status_code == 200
    assert res.json == []


def test_alarms_rejects_bad_limit(client):
    res = client.get("/api/v1/alarms?limit=0")
    assert res.status_code == 400
    assert res.json["error"]["code"] == "BAD_PARAM"

    res = client.get("/api/v1/alarms?limit=banana")
    assert res.status_code == 400
    assert res.json["error"]["code"] == "BAD_PARAM"


# operator HMI --------------------------------------------------------------

def test_operator_page_renders(client):
    res = client.get("/")
    assert res.status_code == 200
    body = res.data.decode()
    # initial server-rendered state visible
    assert "HEALTHY" in body
    assert "fan-01" in body


def test_operator_page_shows_last_alarm(client):
    res = client.get("/")
    body = res.data.decode()
    # most recent fan-01 alarm: IMBALANCE → HEALTHY
    assert "IMBALANCE" in body
    assert "last alarm" in body


def test_operator_page_handles_empty_db(empty_client):
    res = empty_client.get("/")
    assert res.status_code == 200
    # Should render with "—" placeholders, not crash
    assert "—" in res.data.decode()


# About + static ------------------------------------------------------------

def test_about_shows_stats(client):
    res = client.get("/about")
    assert res.status_code == 200
    body = res.data.decode()
    assert "Events persisted" in body
    assert "4" in body  # 4 rows seeded total
