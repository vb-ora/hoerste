"""Rollenrechte: nutzer < admin < superadmin."""

import pytest

from tests.conftest import CHEF_NAME, CHEF_PW, KENNUNG, abfrage, anmelden, konto_anlegen


@pytest.fixture
def konten(cfg, client):
    return {
        "chef": abfrage(cfg, "SELECT id FROM nutzer WHERE name = ?", CHEF_NAME)[0]["id"],
        "ada": konto_anlegen(cfg, "ada", "ada-passwort-1", "admin"),
        "anton": konto_anlegen(cfg, "anton", "anton-passwort", "admin"),
        "nina": konto_anlegen(cfg, "nina", "nina-passwort-1"),
        "nils": konto_anlegen(cfg, "nils", "nils-passwort-1"),
    }


def _als(client, name):
    pw = {"chef": CHEF_PW, "ada": "ada-passwort-1", "anton": "anton-passwort",
          "nina": "nina-passwort-1", "nils": "nils-passwort-1"}[name]
    assert anmelden(client, CHEF_NAME if name == "chef" else name, pw).status_code == 200


def _aktiv(client, nid, aktiv):
    return client.post(f"/api/admin/nutzer/{nid}/aktiv", json={"aktiv": aktiv}, headers=KENNUNG)


def _rolle(client, nid, rolle):
    return client.post(f"/api/admin/nutzer/{nid}/rolle", json={"rolle": rolle}, headers=KENNUNG)


def _pwlink(client, nid):
    return client.post(f"/api/admin/nutzer/{nid}/passwort-link", headers=KENNUNG)


# ---------- Nutzer ----------

def test_nutzer_kommt_nicht_in_die_verwaltung(client, konten):
    _als(client, "nina")
    r = client.get("/admin", follow_redirects=False)
    assert r.status_code == 403
    assert "Verwaltung" not in r.text.split("<main")[0]  # kein Navi-Eintrag
    assert client.post("/api/admin/einladungen", headers=KENNUNG).status_code == 403
    assert _aktiv(client, konten["nils"], False).status_code == 403
    assert _pwlink(client, konten["nils"]).status_code == 403
    assert _rolle(client, konten["nils"], "admin").status_code == 403


# ---------- Admin ----------

def test_admin_sieht_verwaltung_und_laedt_ein(client, konten):
    _als(client, "ada")
    r = client.get("/admin")
    assert r.status_code == 200
    assert "nina" in r.text
    assert client.post("/api/admin/einladungen", headers=KENNUNG).json()["link"].startswith("http")


def test_admin_verwaltet_nutzer(client, cfg, konten, neuer_client):
    nina = neuer_client()
    _als(nina, "nina")
    _als(client, "ada")

    assert _aktiv(client, konten["nina"], False).status_code == 200
    assert abfrage(cfg, "SELECT aktiv FROM nutzer WHERE id = ?", konten["nina"])[0]["aktiv"] == 0
    assert nina.get("/", follow_redirects=False).status_code == 303  # sofort abgemeldet
    assert _aktiv(client, konten["nina"], True).status_code == 200
    assert _pwlink(client, konten["nils"]).status_code == 200


def test_admin_darf_keine_rollen_vergeben(client, konten):
    _als(client, "ada")
    assert _rolle(client, konten["nina"], "admin").status_code == 403


@pytest.mark.parametrize("ziel", ["anton", "chef", "ada"])
def test_admin_darf_admins_superadmin_und_sich_nicht_aendern(client, konten, ziel):
    _als(client, "ada")
    assert _aktiv(client, konten[ziel], False).status_code == 403
    assert _pwlink(client, konten[ziel]).status_code == 403


# ---------- Superadmin ----------

def test_superadmin_ernennt_und_entzieht_admins(client, cfg, konten):
    _als(client, "chef")
    assert _rolle(client, konten["nina"], "admin").status_code == 200
    assert abfrage(cfg, "SELECT rolle FROM nutzer WHERE id = ?", konten["nina"])[0]["rolle"] == "admin"
    assert _rolle(client, konten["ada"], "nutzer").status_code == 200
    assert abfrage(cfg, "SELECT rolle FROM nutzer WHERE id = ?", konten["ada"])[0]["rolle"] == "nutzer"


def test_superadmin_verwaltet_admins(client, konten):
    _als(client, "chef")
    assert _aktiv(client, konten["anton"], False).status_code == 200
    assert _pwlink(client, konten["ada"]).status_code == 200


def test_superadmin_kann_sich_nicht_selbst_aendern(client, konten):
    _als(client, "chef")
    assert _rolle(client, konten["chef"], "nutzer").status_code == 403
    assert _aktiv(client, konten["chef"], False).status_code == 403


def test_keine_zweite_superadmin_rolle_per_api(client, konten):
    _als(client, "chef")
    assert _rolle(client, konten["nina"], "superadmin").status_code == 400


def test_herabgestufter_admin_verliert_rechte_sofort(client, konten, neuer_client):
    ada = neuer_client()
    _als(ada, "ada")
    assert ada.get("/admin").status_code == 200
    _als(client, "chef")
    _rolle(client, konten["ada"], "nutzer")
    assert ada.get("/admin").status_code == 403


def test_admin_seite_zeigt_keine_uebungsdaten(client, konten):
    """Die Verwaltung zeigt nur Kontodaten (Name, Rolle, aktiv, letzter Login)."""
    _als(client, "ada")
    text = client.get("/admin").text.split("<main", 1)[1]
    for wort in ("Box ", "Trefferquote", "Tagesziel", "Toleranz"):
        assert wort not in text
