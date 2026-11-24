from datetime import timedelta

import pytest

from app import db
from app.auth import COOKIE_NAME, LoginBremse, lies_session, sicheres_ziel
from app.config import KonfigFehler, lade_einstellungen, lies_env_datei
from tests.conftest import CHEF_NAME, CHEF_PW, KENNUNG, abfrage, anmelden, konto_anlegen

GESCHUETZT = ["/", "/labor", "/einstellungen", "/admin"]


# ---------- Zugang ----------

@pytest.mark.parametrize("pfad", GESCHUETZT)
def test_geschuetzte_seiten_leiten_auf_login(client, pfad):
    r = client.get(pfad, follow_redirects=False)
    assert r.status_code == 303
    assert r.headers["location"].startswith("/login?weiter=")


@pytest.mark.parametrize("pfad", ["/healthz", "/login", "/static/css/stil.css"])
def test_offene_seiten(client, pfad):
    assert client.get(pfad).status_code == 200


def test_api_ohne_login_gibt_401(client):
    r = client.post("/api/konto/einstellungen", json={}, headers=KENNUNG)
    assert r.status_code == 401


# ---------- Anmelden ----------

def test_login_richtig_setzt_sicheres_cookie(client):
    r = anmelden(client, CHEF_NAME, CHEF_PW)
    assert r.status_code == 200
    assert r.json()["weiter"] == "/"
    kopf = r.headers["set-cookie"].lower()
    assert COOKIE_NAME in kopf and "httponly" in kopf and "samesite=lax" in kopf
    assert client.get("/labor").status_code == 200


def test_login_name_ohne_gross_klein(client):
    assert anmelden(client, CHEF_NAME.upper(), CHEF_PW).status_code == 200


def test_login_falsch(client):
    r = anmelden(client, CHEF_NAME, "falsch-falsch-falsch")
    assert r.status_code == 401
    assert COOKIE_NAME not in r.headers.get("set-cookie", "")
    # gleiche Meldung bei unbekanntem Namen
    assert anmelden(client, "gibtsnicht", "x" * 12).json() == r.json()


def test_login_ohne_kennung_wird_abgelehnt(client):
    r = client.post("/api/login", json={"name": CHEF_NAME, "passwort": CHEF_PW})
    assert r.status_code == 403


def test_login_weiterleitung_nur_lokal(client):
    r = client.post("/api/login", json={"name": CHEF_NAME, "passwort": CHEF_PW,
                                        "weiter": "//boese.example/x"}, headers=KENNUNG)
    assert r.json()["weiter"] == "/"
    assert sicheres_ziel("/labor?a=1") == "/labor?a=1"
    assert sicheres_ziel("https://boese.example") == "/"


def test_logout(client):
    anmelden(client, CHEF_NAME, CHEF_PW)
    assert client.post("/api/logout", headers=KENNUNG).status_code == 200
    assert client.get("/labor", follow_redirects=False).status_code == 303


def test_gefaelschtes_cookie_gilt_nicht(client):
    client.cookies.set(COOKIE_NAME, "manipuliert")
    assert client.get("/", follow_redirects=False).status_code == 303


def test_deaktiviertes_konto_kann_sich_nicht_anmelden(client, cfg):
    konto_anlegen(cfg, "otto", "otto-passwort-1")
    with db.verbinde(cfg.db_pfad) as conn:
        conn.execute("UPDATE nutzer SET aktiv = 0 WHERE name = 'otto'")
    assert anmelden(client, "otto", "otto-passwort-1").status_code == 401


# ---------- Login-Bremse ----------

def test_bremse_sperrt_nach_fuenf_fehlversuchen(client):
    for _ in range(5):
        assert anmelden(client, CHEF_NAME, "falsch-falsch-falsch").status_code == 401
    r = anmelden(client, CHEF_NAME, CHEF_PW)  # auch das richtige Passwort ist jetzt gesperrt
    assert r.status_code == 429
    assert "15 Minuten" in r.json()["detail"]
    # anderer Name ist nicht betroffen
    assert anmelden(client, "jemand", "x" * 12).status_code == 401


def test_bremse_laeuft_nach_15_minuten_ab():
    uhr = [1000.0]
    bremse = LoginBremse(uhr=lambda: uhr[0])
    k = bremse.schluessel("Anna", "1.2.3.4")
    for _ in range(4):
        bremse.fehlschlag(k)
    assert bremse.rest_sperre(k) == 0
    bremse.fehlschlag(k)
    assert bremse.rest_sperre(k) == pytest.approx(900)
    uhr[0] += 899
    assert bremse.rest_sperre(k) > 0
    uhr[0] += 2
    assert bremse.rest_sperre(k) == 0


def test_bremse_alte_fehlversuche_verfallen():
    uhr = [0.0]
    bremse = LoginBremse(uhr=lambda: uhr[0])
    k = bremse.schluessel("anna", "ip")
    for _ in range(4):
        bremse.fehlschlag(k)
    uhr[0] += 16 * 60
    bremse.fehlschlag(k)
    assert bremse.rest_sperre(k) == 0


def test_bremse_erfolg_setzt_zurueck():
    bremse = LoginBremse()
    k = bremse.schluessel("anna", "ip")
    for _ in range(4):
        bremse.fehlschlag(k)
    bremse.erfolg(k)
    bremse.fehlschlag(k)
    assert bremse.rest_sperre(k) == 0


# ---------- Einladung ----------

def _einladen(client) -> str:
    anmelden(client, CHEF_NAME, CHEF_PW)
    link = client.post("/api/admin/einladungen", headers=KENNUNG).json()["link"]
    client.post("/api/logout", headers=KENNUNG)
    return link.split("/einladung/")[1]


def _einloesen(c, token, name="berta", pw="berta-passwort-1", pw2=None):
    return c.post(f"/api/einladung/{token}",
                  json={"name": name, "passwort": pw, "passwort2": pw2 or pw}, headers=KENNUNG)


def test_einladung_einloesen_legt_konto_an(client, cfg):
    token = _einladen(client)
    assert client.get(f"/einladung/{token}").status_code == 200
    r = _einloesen(client, token)
    assert r.status_code == 200
    assert client.get("/einstellungen").status_code == 200  # direkt angemeldet
    zeile = abfrage(cfg, "SELECT rolle FROM nutzer WHERE name = 'berta'")[0]
    assert zeile["rolle"] == "nutzer"
    assert len(abfrage(cfg, "SELECT * FROM einstellung")) == 2


def test_einladung_nur_einmal(client, neuer_client):
    token = _einladen(client)
    assert _einloesen(client, token).status_code == 200
    zweiter = neuer_client()
    assert _einloesen(zweiter, token, name="carl").status_code == 410
    assert zweiter.get(f"/einladung/{token}").status_code == 410


def test_einladung_abgelaufen(client, cfg):
    token = _einladen(client)
    with db.verbinde(cfg.db_pfad) as conn:
        conn.execute("UPDATE einladung SET gueltig_bis = ?", (db.iso(db.jetzt() - timedelta(minutes=1)),))
    assert _einloesen(client, token).status_code == 410


def test_einladung_zurueckgezogen(client, cfg):
    token = _einladen(client)
    anmelden(client, CHEF_NAME, CHEF_PW)
    eid = abfrage(cfg, "SELECT id FROM einladung")[0]["id"]
    assert client.post(f"/api/admin/einladungen/{eid}/zurueckziehen", headers=KENNUNG).status_code == 200
    assert abfrage(cfg, "SELECT aktiv FROM einladung")[0]["aktiv"] == 0  # Soft-Delete
    assert _einloesen(client, token).status_code == 410


def test_einladung_name_vergeben(client):
    token = _einladen(client)
    r = _einloesen(client, token, name=CHEF_NAME.upper())
    assert r.status_code == 409
    assert _einloesen(client, token, name="dora").status_code == 200  # Einladung noch gültig


@pytest.mark.parametrize("name,pw,pw2", [
    ("emil", "kurz", None),
    ("emil", "emil-passwort-1", "anderes-passwort"),
    ("e", "emil-passwort-1", None),
    ("emil", "ä" * 40, None),  # mehr als 72 Byte
])
def test_einladung_eingaben_pruefen(client, name, pw, pw2):
    token = _einladen(client)
    assert _einloesen(client, token, name=name, pw=pw, pw2=pw2).status_code == 400


def test_einladungstoken_nicht_im_klartext_gespeichert(client, cfg):
    token = _einladen(client)
    assert abfrage(cfg, "SELECT token FROM einladung")[0]["token"] != token


# ---------- Passwort und Sitzungen ----------

def test_passwort_aendern_meldet_andere_geraete_ab(client, cfg, neuer_client):
    konto_anlegen(cfg, "otto", "otto-passwort-1")
    handy = neuer_client()
    anmelden(client, "otto", "otto-passwort-1")
    anmelden(handy, "otto", "otto-passwort-1")

    r = client.post("/api/konto/passwort", headers=KENNUNG,
                    json={"alt": "otto-passwort-1", "neu": "otto-passwort-2", "neu2": "otto-passwort-2"})
    assert r.status_code == 200
    assert client.get("/einstellungen", follow_redirects=False).status_code == 200
    assert handy.get("/einstellungen", follow_redirects=False).status_code == 303
    assert anmelden(handy, "otto", "otto-passwort-2").status_code == 200


def test_passwort_aendern_altes_falsch(client, cfg):
    konto_anlegen(cfg, "otto", "otto-passwort-1")
    anmelden(client, "otto", "otto-passwort-1")
    r = client.post("/api/konto/passwort", headers=KENNUNG,
                    json={"alt": "falsch-falsch", "neu": "otto-passwort-2", "neu2": "otto-passwort-2"})
    assert r.status_code == 400


def test_passwort_link(client, cfg, neuer_client):
    konto_anlegen(cfg, "otto", "otto-passwort-1")
    otto = neuer_client()
    anmelden(otto, "otto", "otto-passwort-1")

    anmelden(client, CHEF_NAME, CHEF_PW)
    oid = abfrage(cfg, "SELECT id FROM nutzer WHERE name = 'otto'")[0]["id"]
    link = client.post(f"/api/admin/nutzer/{oid}/passwort-link", headers=KENNUNG).json()["link"]
    token = link.split("/passwort/")[1]

    fremd = neuer_client()
    assert fremd.get(f"/passwort/{token}").status_code == 200
    r = fremd.post(f"/api/passwort-link/{token}", headers=KENNUNG,
                   json={"passwort": "otto-neu-12345", "passwort2": "otto-neu-12345"})
    assert r.status_code == 200
    assert fremd.get("/einstellungen").status_code == 200
    assert otto.get("/einstellungen", follow_redirects=False).status_code == 303  # alte Sitzung weg
    assert anmelden(neuer_client(), "otto", "otto-neu-12345").status_code == 200
    # nur einmal nutzbar
    assert fremd.get(f"/passwort/{token}").status_code == 410


def test_neuer_passwort_link_entwertet_alten(client, cfg):
    konto_anlegen(cfg, "otto", "otto-passwort-1")
    anmelden(client, CHEF_NAME, CHEF_PW)
    oid = abfrage(cfg, "SELECT id FROM nutzer WHERE name = 'otto'")[0]["id"]
    alt = client.post(f"/api/admin/nutzer/{oid}/passwort-link", headers=KENNUNG).json()["link"]
    client.post(f"/api/admin/nutzer/{oid}/passwort-link", headers=KENNUNG)
    assert client.get(alt.replace("http://testserver", "")).status_code == 410


def test_superadmin_passwort_nur_ueber_env(client):
    anmelden(client, CHEF_NAME, CHEF_PW)
    r = client.post("/api/konto/passwort", headers=KENNUNG,
                    json={"alt": CHEF_PW, "neu": "x" * 12, "neu2": "x" * 12})
    assert r.status_code == 400


# ---------- Einstellungen ----------

def test_einstellungen_speichern(client, cfg):
    anmelden(client, CHEF_NAME, CHEF_PW)
    daten = {"h_system": "B", "vorzeichen": "zeichen", "klang": "klavier",
             "tagesziel_min": 10, "toleranz_cent": 15}
    assert client.post("/api/konto/einstellungen", json=daten, headers=KENNUNG).status_code == 200
    zeile = abfrage(cfg, "SELECT h_system, vorzeichen, klang, tagesziel_min, toleranz_cent FROM einstellung")[0]
    assert tuple(zeile) == ("B", "zeichen", "klavier", 10, 15)
    assert 'value="B" checked' in client.get("/einstellungen").text


@pytest.mark.parametrize("feld,wert", [
    ("h_system", "X"), ("vorzeichen", "beides"), ("klang", "orgel"),
    ("tagesziel_min", 0), ("toleranz_cent", 30),
])
def test_einstellungen_ungueltig(client, feld, wert):
    anmelden(client, CHEF_NAME, CHEF_PW)
    daten = {"h_system": "H", "vorzeichen": "silben", "klang": "synth",
             "tagesziel_min": 5, "toleranz_cent": 25, feld: wert}
    assert client.post("/api/konto/einstellungen", json=daten, headers=KENNUNG).status_code == 400


# ---------- Konfiguration ----------

def test_env_datei_verdoppelte_dollar(tmp_path):
    datei = tmp_path / ".env"
    datei.write_text("# Kommentar\nHOERSTE_A=$$2b$$12$$abc\nHOERSTE_B=\"mit leer\"\n", encoding="utf-8")
    assert lies_env_datei(datei) == {"HOERSTE_A": "$2b$12$abc", "HOERSTE_B": "mit leer"}


def test_konfig_ohne_secret_bricht_ab(tmp_path, monkeypatch):
    for k in list(__import__("os").environ):
        if k.startswith("HOERSTE_"):
            monkeypatch.delenv(k)
    with pytest.raises(KonfigFehler):
        lade_einstellungen(env_datei=tmp_path / "fehlt.env")


def test_session_cookie_mit_anderem_schluessel_ungueltig(client, cfg):
    from dataclasses import replace
    r = anmelden(client, CHEF_NAME, CHEF_PW)
    wert = r.cookies[COOKIE_NAME]
    assert lies_session(cfg, wert) is not None
    assert lies_session(replace(cfg, secret_key="anderer-schluessel-" + "y" * 40), wert) is None
