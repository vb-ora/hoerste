"""Passwort-Hash, Session-Cookie, Login-Bremse, Rollen und Abhängigkeiten."""

from __future__ import annotations

import hashlib
import secrets
import sqlite3
import time
from collections.abc import Callable, Iterator

import bcrypt
from fastapi import Depends, HTTPException, Request, Response
from itsdangerous import BadSignature, URLSafeTimedSerializer

from app.config import Einstellungen
from app.db import iso, jetzt, verbinde

COOKIE_NAME = "hoerste_session"
COOKIE_TAGE = 30
MIN_PASSWORT = 10
MAX_PASSWORT_BYTES = 72  # Grenze von bcrypt
ROLLEN = ("superadmin", "admin", "nutzer")

# Zum Ausgleich der Laufzeit, wenn ein Name nicht existiert.
_DUMMY_HASH = bcrypt.hashpw(b"hoerste-dummy-passwort", bcrypt.gensalt(4))


# ---------- Ausnahmen (Behandlung in main.py) ----------

class LoginNoetig(Exception):
    pass


class Verweigert(Exception):
    pass


# ---------- Passwörter und Tokens ----------

def passwort_fehler(passwort: str) -> str | None:
    if len(passwort) < MIN_PASSWORT:
        return f"Das Passwort braucht mindestens {MIN_PASSWORT} Zeichen."
    if len(passwort.encode("utf-8")) > MAX_PASSWORT_BYTES:
        return "Das Passwort ist zu lang (höchstens 72 Byte)."
    return None


def passwort_hash(passwort: str, runden: int = 12) -> str:
    return bcrypt.hashpw(passwort.encode("utf-8"), bcrypt.gensalt(runden)).decode()


def passwort_pruefen(passwort: str, gespeichert: str | None) -> bool:
    roh = passwort.encode("utf-8")
    if len(roh) > MAX_PASSWORT_BYTES:
        roh = roh[:MAX_PASSWORT_BYTES]
        gespeichert = None
    if not gespeichert:
        bcrypt.checkpw(roh, _DUMMY_HASH)
        return False
    try:
        return bcrypt.checkpw(roh, gespeichert.encode())
    except ValueError:
        return False


def neues_token() -> tuple[str, str]:
    """Gibt (Klartext für den Link, Hash für die DB) zurück."""
    klar = secrets.token_urlsafe(32)
    return klar, token_hash(klar)


def token_hash(klar: str) -> str:
    return hashlib.sha256(klar.encode()).hexdigest()


# ---------- Session-Cookie ----------

def _serializer(cfg: Einstellungen) -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(cfg.secret_key, salt="hoerste-session")


def setze_session(response: Response, cfg: Einstellungen, nutzer_id: int, stand: int) -> None:
    wert = _serializer(cfg).dumps({"n": nutzer_id, "s": stand})
    response.set_cookie(
        COOKIE_NAME,
        wert,
        max_age=COOKIE_TAGE * 86400,
        httponly=True,
        secure=cfg.cookie_secure,
        samesite="lax",
        path="/",
    )


def loesche_session(response: Response, cfg: Einstellungen) -> None:
    response.delete_cookie(COOKIE_NAME, path="/", secure=cfg.cookie_secure, httponly=True, samesite="lax")


def lies_session(cfg: Einstellungen, wert: str | None) -> tuple[int, int] | None:
    if not wert:
        return None
    try:
        daten = _serializer(cfg).loads(wert, max_age=COOKIE_TAGE * 86400)
        return int(daten["n"]), int(daten["s"])
    except (BadSignature, KeyError, TypeError, ValueError):
        return None


# ---------- Login-Bremse (im Arbeitsspeicher) ----------

class LoginBremse:
    """5 Fehlversuche pro Name und IP → 15 Minuten Sperre."""

    def __init__(self, max_versuche: int = 5, sperre_s: float = 15 * 60,
                 uhr: Callable[[], float] = time.monotonic):
        self.max_versuche = max_versuche
        self.sperre_s = sperre_s
        self.uhr = uhr
        self._fehler: dict[tuple[str, str], list[float]] = {}
        self._gesperrt: dict[tuple[str, str], float] = {}

    @staticmethod
    def schluessel(name: str, ip: str) -> tuple[str, str]:
        return name.strip().casefold(), ip

    def rest_sperre(self, schluessel: tuple[str, str]) -> float:
        bis = self._gesperrt.get(schluessel)
        if bis is None:
            return 0.0
        rest = bis - self.uhr()
        if rest <= 0:
            del self._gesperrt[schluessel]
            return 0.0
        return rest

    def fehlschlag(self, schluessel: tuple[str, str]) -> None:
        jetzt_s = self.uhr()
        liste = [t for t in self._fehler.get(schluessel, []) if jetzt_s - t < self.sperre_s]
        liste.append(jetzt_s)
        if len(liste) >= self.max_versuche:
            self._gesperrt[schluessel] = jetzt_s + self.sperre_s
            self._fehler.pop(schluessel, None)
        else:
            self._fehler[schluessel] = liste

    def erfolg(self, schluessel: tuple[str, str]) -> None:
        self._fehler.pop(schluessel, None)
        self._gesperrt.pop(schluessel, None)


# ---------- Rechte ----------

def darf_verwalten(akteur: sqlite3.Row, ziel: sqlite3.Row) -> bool:
    """Admins verwalten nur einfache Nutzer, der Superadmin alle außer sich selbst."""
    if akteur["id"] == ziel["id"]:
        return False
    if akteur["rolle"] == "superadmin":
        return ziel["rolle"] != "superadmin"
    if akteur["rolle"] == "admin":
        return ziel["rolle"] == "nutzer"
    return False


def darf_rolle_aendern(akteur: sqlite3.Row, ziel: sqlite3.Row) -> bool:
    return akteur["rolle"] == "superadmin" and darf_verwalten(akteur, ziel)


# ---------- Superadmin aus .env ----------

def einstellung_sicherstellen(conn: sqlite3.Connection, nutzer_id: int) -> None:
    conn.execute("INSERT OR IGNORE INTO einstellung (nutzer_id) VALUES (?)", (nutzer_id,))


def superadmin_abgleichen(conn: sqlite3.Connection, cfg: Einstellungen) -> int:
    with conn:
        zeile = conn.execute(
            "SELECT id, passwort_hash FROM nutzer WHERE name = ?", (cfg.superadmin_name,)
        ).fetchone()
        if zeile:
            sid = zeile["id"]
            neuer_stand = 1 if zeile["passwort_hash"] != cfg.superadmin_hash else 0
            conn.execute(
                "UPDATE nutzer SET rolle = 'superadmin', passwort_hash = ?, aktiv = 1, "
                "sitzungs_stand = sitzungs_stand + ? WHERE id = ?",
                (cfg.superadmin_hash, neuer_stand, sid),
            )
        else:
            sid = conn.execute(
                "INSERT INTO nutzer (name, passwort_hash, rolle) VALUES (?, ?, 'superadmin')",
                (cfg.superadmin_name, cfg.superadmin_hash),
            ).lastrowid
        # Genau ein Superadmin: frühere werden zu Admins.
        conn.execute("UPDATE nutzer SET rolle = 'admin' WHERE rolle = 'superadmin' AND id != ?", (sid,))
        einstellung_sicherstellen(conn, sid)
    return sid


# ---------- Abhängigkeiten ----------

def hole_cfg(request: Request) -> Einstellungen:
    return request.app.state.cfg


def hole_db(request: Request) -> Iterator[sqlite3.Connection]:
    conn = verbinde(request.app.state.cfg.db_pfad)
    try:
        yield conn
    finally:
        conn.close()


def aktueller_nutzer(request: Request, conn: sqlite3.Connection = Depends(hole_db)) -> sqlite3.Row | None:
    sitzung = lies_session(request.app.state.cfg, request.cookies.get(COOKIE_NAME))
    if not sitzung:
        return None
    nutzer_id, stand = sitzung
    zeile = conn.execute(
        "SELECT * FROM nutzer WHERE id = ? AND aktiv = 1", (nutzer_id,)
    ).fetchone()
    if not zeile or zeile["sitzungs_stand"] != stand:
        return None
    return zeile


def angemeldet(nutzer: sqlite3.Row | None = Depends(aktueller_nutzer)) -> sqlite3.Row:
    if nutzer is None:
        raise LoginNoetig()
    return nutzer


def nur_admin(nutzer: sqlite3.Row = Depends(angemeldet)) -> sqlite3.Row:
    if nutzer["rolle"] not in ("admin", "superadmin"):
        raise Verweigert()
    return nutzer


def nur_superadmin(nutzer: sqlite3.Row = Depends(angemeldet)) -> sqlite3.Row:
    if nutzer["rolle"] != "superadmin":
        raise Verweigert()
    return nutzer


def schreibschutz(request: Request) -> None:
    """CSRF-Schutz zusammen mit SameSite=Lax: schreibende Aufrufe nur mit X-Hoerste: 1."""
    if request.method not in ("GET", "HEAD", "OPTIONS") and request.headers.get("x-hoerste") != "1":
        raise HTTPException(403, "Anfrage ohne Kennung X-Hoerste abgelehnt.")


def letzter_login_setzen(conn: sqlite3.Connection, nutzer_id: int) -> None:
    with conn:
        conn.execute("UPDATE nutzer SET letzter_login = ? WHERE id = ?", (iso(jetzt()), nutzer_id))


def sicheres_ziel(weiter: str | None) -> str:
    """Nur lokale Pfade als Weiterleitungsziel (kein offener Redirect)."""
    if weiter and weiter.startswith("/") and not weiter.startswith("//") and "\\" not in weiter:
        return weiter
    return "/"
