import re
import sqlite3
from dataclasses import replace
from datetime import datetime
from pathlib import Path

from fastapi.testclient import TestClient

from app import db, schema
from app.auth import superadmin_abgleichen
from app.main import erstelle_app
from tests.conftest import CHEF_NAME, abfrage, schneller_hash


def _schema_bild(conn):
    tabellen = conn.execute("SELECT name, sql FROM sqlite_master ORDER BY name").fetchall()
    return [(t["name"], t["sql"]) for t in tabellen]


def test_migration_legt_tabellen_an_und_ist_wiederholbar(tmp_path):
    conn = db.verbinde(tmp_path / "t.db")
    schema.migriere(conn)
    vorher = _schema_bild(conn)
    schema.migriere(conn)
    schema.migriere(conn)
    assert _schema_bild(conn) == vorher
    namen = {n for n, _ in vorher}
    assert {"nutzer", "einladung", "einstellung", "passwort_link"} <= namen
    assert "sitzungs_stand" in db.spalten(conn, "nutzer")
    assert {"stimmlage", "umfang_tief", "umfang_hoch"} <= db.spalten(conn, "einstellung")


def test_migration_ergaenzt_fehlende_spalte_und_behaelt_daten(tmp_path):
    conn = db.verbinde(tmp_path / "alt.db")
    # Stand ohne sitzungs_stand, wie eine ältere Datenbank
    conn.execute(
        "CREATE TABLE nutzer (id INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE COLLATE NOCASE, "
        "passwort_hash TEXT NOT NULL, rolle TEXT NOT NULL DEFAULT 'nutzer', letzter_login TEXT, "
        "erstellt_am TEXT NOT NULL DEFAULT 'x', aktiv INTEGER NOT NULL DEFAULT 1)"
    )
    conn.execute("INSERT INTO nutzer (name, passwort_hash) VALUES ('anna', 'h')")
    conn.commit()
    assert "sitzungs_stand" not in db.spalten(conn, "nutzer")

    schema.migriere(conn)

    assert "sitzungs_stand" in db.spalten(conn, "nutzer")
    zeile = conn.execute("SELECT name, passwort_hash, sitzungs_stand FROM nutzer").fetchone()
    assert tuple(zeile) == ("anna", "h", 0)


def test_spalte_ergaenzen_meldet_ob_etwas_passiert_ist(tmp_path):
    conn = db.verbinde(tmp_path / "t.db")
    conn.execute("CREATE TABLE probe (id INTEGER PRIMARY KEY)")
    assert db.spalte_ergaenzen(conn, "probe", "neu", "TEXT") is True
    assert db.spalte_ergaenzen(conn, "probe", "neu", "TEXT") is False


def test_kein_drop_und_kein_delete_im_code():
    app_dir = Path(__file__).resolve().parent.parent / "app"
    verboten = re.compile(r"\b(DROP\s+TABLE|DELETE\s+FROM|DROP\s+COLUMN|RENAME\s+(COLUMN|TO))\b", re.I)
    funde = [str(p) for p in app_dir.rglob("*.py") if verboten.search(p.read_text(encoding="utf-8"))]
    assert funde == []


def test_backup_beim_start_und_nur_die_letzten_zehn(tmp_path):
    db_pfad = tmp_path / "hoerste.db"
    backups = tmp_path / "backups"
    assert db.backup(db_pfad, backups, 10) is None  # noch keine DB → kein Backup

    conn = sqlite3.connect(db_pfad)
    conn.execute("CREATE TABLE probe (wert TEXT)")
    conn.execute("INSERT INTO probe VALUES ('drin')")
    conn.commit()
    conn.close()

    backups.mkdir()
    for i in range(12):
        (backups / f"hoerste_20200101_0000{i:02d}.db").write_bytes(b"alt")

    ziel = db.backup(db_pfad, backups, 10, zeit=datetime(2026, 11, 24, 12, 0, 0))
    assert ziel.name == "hoerste_20261124_120000.db"
    dateien = sorted(p.name for p in backups.glob("hoerste_*.db"))
    assert len(dateien) == 10
    assert dateien[-1] == "hoerste_20261124_120000.db"
    kopie = sqlite3.connect(ziel)
    assert kopie.execute("SELECT wert FROM probe").fetchone()[0] == "drin"
    kopie.close()


def test_app_start_macht_backup_migration_superadmin(cfg):
    with TestClient(erstelle_app(cfg)):
        pass
    assert cfg.db_pfad.is_file()
    assert list(cfg.backup_dir.glob("*.db")) == []  # erster Start: noch nichts zu sichern
    chef = abfrage(cfg, "SELECT rolle, aktiv FROM nutzer WHERE name = ?", CHEF_NAME)
    assert [tuple(z) for z in chef] == [("superadmin", 1)]
    assert len(abfrage(cfg, "SELECT * FROM einstellung")) == 1

    with TestClient(erstelle_app(cfg)):
        pass
    assert len(list(cfg.backup_dir.glob("hoerste_*.db"))) == 1
    assert len(abfrage(cfg, "SELECT * FROM nutzer")) == 1


def test_superadmin_wechsel_hinterlaesst_genau_einen(cfg):
    cfg.db_pfad.parent.mkdir(parents=True)
    conn = db.verbinde(cfg.db_pfad)
    schema.migriere(conn)
    alt_id = superadmin_abgleichen(conn, cfg)

    neu = replace(cfg, superadmin_name="neuchef", superadmin_hash=schneller_hash("anderes-passwort"))
    neu_id = superadmin_abgleichen(conn, neu)

    rollen = dict(conn.execute("SELECT id, rolle FROM nutzer").fetchall())
    assert rollen == {alt_id: "admin", neu_id: "superadmin"}


def test_superadmin_passwortwechsel_erhoeht_sitzungsstand(cfg):
    cfg.db_pfad.parent.mkdir(parents=True)
    conn = db.verbinde(cfg.db_pfad)
    schema.migriere(conn)
    sid = superadmin_abgleichen(conn, cfg)
    superadmin_abgleichen(conn, cfg)  # gleicher Hash → kein Wechsel
    stand = lambda: conn.execute("SELECT sitzungs_stand FROM nutzer WHERE id = ?", (sid,)).fetchone()[0]
    assert stand() == 0
    superadmin_abgleichen(conn, replace(cfg, superadmin_hash=schneller_hash("neues-passwort-1")))
    assert stand() == 1


def test_superadmin_wird_reaktiviert(cfg):
    cfg.db_pfad.parent.mkdir(parents=True)
    conn = db.verbinde(cfg.db_pfad)
    schema.migriere(conn)
    sid = superadmin_abgleichen(conn, cfg)
    with conn:
        conn.execute("UPDATE nutzer SET aktiv = 0 WHERE id = ?", (sid,))
    superadmin_abgleichen(conn, cfg)
    assert conn.execute("SELECT aktiv FROM nutzer WHERE id = ?", (sid,)).fetchone()[0] == 1
