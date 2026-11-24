from __future__ import annotations

import bcrypt
import pytest
from fastapi.testclient import TestClient

from app import db
from app.config import Einstellungen
from app.main import erstelle_app

CHEF_NAME = "chef"
CHEF_PW = "chef-passwort-123"
KENNUNG = {"X-Hoerste": "1"}


def schneller_hash(passwort: str) -> str:
    return bcrypt.hashpw(passwort.encode(), bcrypt.gensalt(4)).decode()


@pytest.fixture
def cfg(tmp_path) -> Einstellungen:
    return Einstellungen(
        daten_dir=tmp_path / "data",
        secret_key="test-geheimnis-" + "x" * 40,
        superadmin_name=CHEF_NAME,
        superadmin_hash=schneller_hash(CHEF_PW),
        cookie_secure=False,
        bcrypt_runden=4,
    )


@pytest.fixture
def client(cfg):
    with TestClient(erstelle_app(cfg)) as c:
        yield c


@pytest.fixture
def neuer_client(client):
    """Weitere Browser-Sitzungen auf derselben App (ohne erneuten Lifespan)."""
    def machen() -> TestClient:
        return TestClient(client.app)
    return machen


def anmelden(c: TestClient, name: str, passwort: str):
    return c.post("/api/login", json={"name": name, "passwort": passwort}, headers=KENNUNG)


def konto_anlegen(cfg: Einstellungen, name: str, passwort: str, rolle: str = "nutzer") -> int:
    conn = db.verbinde(cfg.db_pfad)
    try:
        with conn:
            nid = conn.execute(
                "INSERT INTO nutzer (name, passwort_hash, rolle) VALUES (?, ?, ?)",
                (name, schneller_hash(passwort), rolle),
            ).lastrowid
            conn.execute("INSERT INTO einstellung (nutzer_id) VALUES (?)", (nid,))
        return nid
    finally:
        conn.close()


def abfrage(cfg: Einstellungen, sql: str, *werte):
    conn = db.verbinde(cfg.db_pfad)
    try:
        return conn.execute(sql, werte).fetchall()
    finally:
        conn.close()
