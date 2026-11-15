from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_healthz():
    r = client.get("/healthz")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_labor_liefert_seite():
    r = client.get("/labor")
    assert r.status_code == 200
    assert "Labor" in r.text
    assert "/static/js/labor.js" in r.text


def test_vendor_dateien_vorhanden():
    for pfad in (
        "/static/js/vendor/pitchy/pitchy.js",
        "/static/js/vendor/fft/fft.js",
        "/static/js/vendor/pitchy/LICENSE",
        "/static/js/vendor/fft/LICENSE",
    ):
        assert client.get(pfad).status_code == 200, pfad
