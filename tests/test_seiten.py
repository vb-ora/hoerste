from tests.conftest import CHEF_NAME, CHEF_PW, anmelden


def test_healthz(client):
    r = client.get("/healthz")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_labor_nur_mit_login(client):
    r = client.get("/labor", follow_redirects=False)
    assert r.status_code == 303
    assert r.headers["location"] == "/login?weiter=/labor"
    anmelden(client, CHEF_NAME, CHEF_PW)
    r = client.get("/labor")
    assert r.status_code == 200
    assert "/static/js/labor.js" in r.text


def test_login_seite_leitet_angemeldete_weiter(client):
    anmelden(client, CHEF_NAME, CHEF_PW)
    r = client.get("/login?weiter=/labor", follow_redirects=False)
    assert r.status_code == 303
    assert r.headers["location"] == "/labor"


def test_vendor_dateien_vorhanden(client):
    for pfad in (
        "/static/js/vendor/pitchy/pitchy.js",
        "/static/js/vendor/fft/fft.js",
        "/static/js/vendor/pitchy/LICENSE",
        "/static/js/vendor/fft/LICENSE",
        "/static/img/logo.svg",
    ):
        assert client.get(pfad).status_code == 200, pfad
