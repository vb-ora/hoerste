"""Anmelden, Abmelden, Einladung einlösen, Passwort und Einstellungen."""

from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field

from app.auth import (
    LoginBremse,
    angemeldet,
    einstellung_sicherstellen,
    hole_cfg,
    hole_db,
    letzter_login_setzen,
    loesche_session,
    passwort_fehler,
    passwort_hash,
    passwort_pruefen,
    schreibschutz,
    setze_session,
    sicheres_ziel,
    token_hash,
)
from app.config import Einstellungen
from app.db import aus_iso, iso, jetzt

router = APIRouter(prefix="/api", dependencies=[Depends(schreibschutz)])

MAX_NAME = 40


# ---------- Hilfen für Einladungen und Passwort-Links ----------

def einladung_finden(conn: sqlite3.Connection, klar: str) -> sqlite3.Row | None:
    zeile = conn.execute(
        "SELECT * FROM einladung WHERE token = ? AND aktiv = 1 AND eingeloest_am IS NULL",
        (token_hash(klar),),
    ).fetchone()
    if not zeile or aus_iso(zeile["gueltig_bis"]) < jetzt():
        return None
    return zeile


def passwort_link_finden(conn: sqlite3.Connection, klar: str) -> sqlite3.Row | None:
    zeile = conn.execute(
        "SELECT p.*, n.name AS nutzer_name FROM passwort_link p JOIN nutzer n ON n.id = p.nutzer_id "
        "WHERE p.token = ? AND p.aktiv = 1 AND p.eingeloest_am IS NULL AND n.aktiv = 1",
        (token_hash(klar),),
    ).fetchone()
    if not zeile or aus_iso(zeile["gueltig_bis"]) < jetzt():
        return None
    return zeile


def _passwort_oder_fehler(passwort: str, wiederholung: str | None = None) -> None:
    if wiederholung is not None and passwort != wiederholung:
        raise HTTPException(400, "Die beiden Passwörter stimmen nicht überein.")
    fehler = passwort_fehler(passwort)
    if fehler:
        raise HTTPException(400, fehler)


# ---------- Anmelden / Abmelden ----------

class LoginDaten(BaseModel):
    name: str = Field(max_length=200)
    passwort: str = Field(max_length=500)
    weiter: str | None = None


@router.post("/login")
def login(daten: LoginDaten, request: Request, response: Response,
          conn: sqlite3.Connection = Depends(hole_db), cfg: Einstellungen = Depends(hole_cfg)):
    bremse: LoginBremse = request.app.state.bremse
    ip = request.client.host if request.client else "?"
    schluessel = bremse.schluessel(daten.name, ip)
    rest = bremse.rest_sperre(schluessel)
    if rest > 0:
        minuten = int(rest // 60) + 1
        raise HTTPException(429, f"Zu viele Fehlversuche. Bitte in {minuten} Minuten erneut versuchen.")

    zeile = conn.execute(
        "SELECT * FROM nutzer WHERE name = ? AND aktiv = 1", (daten.name.strip(),)
    ).fetchone()
    if not passwort_pruefen(daten.passwort, zeile["passwort_hash"] if zeile else None):
        bremse.fehlschlag(schluessel)
        raise HTTPException(401, "Name oder Passwort stimmt nicht.")

    bremse.erfolg(schluessel)
    letzter_login_setzen(conn, zeile["id"])
    setze_session(response, cfg, zeile["id"], zeile["sitzungs_stand"])
    return {"ok": True, "weiter": sicheres_ziel(daten.weiter)}


@router.post("/logout")
def logout(response: Response, cfg: Einstellungen = Depends(hole_cfg)):
    loesche_session(response, cfg)
    return {"ok": True, "weiter": "/login"}


# ---------- Einladung einlösen ----------

class EinladungDaten(BaseModel):
    name: str = Field(max_length=200)
    passwort: str = Field(max_length=500)
    passwort2: str = Field(max_length=500)


@router.post("/einladung/{token}")
def einladung_einloesen(token: str, daten: EinladungDaten, response: Response,
                        conn: sqlite3.Connection = Depends(hole_db),
                        cfg: Einstellungen = Depends(hole_cfg)):
    einladung = einladung_finden(conn, token)
    if not einladung:
        raise HTTPException(410, "Diese Einladung ist abgelaufen oder wurde schon benutzt.")
    name = " ".join(daten.name.split())
    if not (2 <= len(name) <= MAX_NAME):
        raise HTTPException(400, f"Der Name braucht 2 bis {MAX_NAME} Zeichen.")
    _passwort_oder_fehler(daten.passwort, daten.passwort2)

    try:
        with conn:
            nid = conn.execute(
                "INSERT INTO nutzer (name, passwort_hash, rolle, letzter_login) VALUES (?, ?, 'nutzer', ?)",
                (name, passwort_hash(daten.passwort, cfg.bcrypt_runden), iso(jetzt())),
            ).lastrowid
            einstellung_sicherstellen(conn, nid)
            geaendert = conn.execute(
                "UPDATE einladung SET eingeloest_von = ?, eingeloest_am = ? "
                "WHERE id = ? AND eingeloest_am IS NULL",
                (nid, iso(jetzt()), einladung["id"]),
            ).rowcount
            if geaendert != 1:
                raise HTTPException(410, "Diese Einladung wurde gerade schon benutzt.")
    except sqlite3.IntegrityError:
        raise HTTPException(409, "Diesen Namen gibt es schon. Bitte einen anderen wählen.")

    setze_session(response, cfg, nid, 0)
    return {"ok": True, "weiter": "/"}


# ---------- Passwort-Link einlösen ----------

class NeuesPasswort(BaseModel):
    passwort: str = Field(max_length=500)
    passwort2: str = Field(max_length=500)


@router.post("/passwort-link/{token}")
def passwort_link_einloesen(token: str, daten: NeuesPasswort, response: Response,
                            conn: sqlite3.Connection = Depends(hole_db),
                            cfg: Einstellungen = Depends(hole_cfg)):
    link = passwort_link_finden(conn, token)
    if not link:
        raise HTTPException(410, "Dieser Link ist abgelaufen oder wurde schon benutzt.")
    _passwort_oder_fehler(daten.passwort, daten.passwort2)
    with conn:
        conn.execute("UPDATE passwort_link SET eingeloest_am = ? WHERE id = ?", (iso(jetzt()), link["id"]))
        conn.execute(
            "UPDATE nutzer SET passwort_hash = ?, sitzungs_stand = sitzungs_stand + 1, letzter_login = ? "
            "WHERE id = ?",
            (passwort_hash(daten.passwort, cfg.bcrypt_runden), iso(jetzt()), link["nutzer_id"]),
        )
    stand = conn.execute("SELECT sitzungs_stand FROM nutzer WHERE id = ?", (link["nutzer_id"],)).fetchone()[0]
    setze_session(response, cfg, link["nutzer_id"], stand)
    return {"ok": True, "weiter": "/"}


# ---------- Eigenes Konto ----------

class PasswortAendern(BaseModel):
    alt: str = Field(max_length=500)
    neu: str = Field(max_length=500)
    neu2: str = Field(max_length=500)


@router.post("/konto/passwort")
def passwort_aendern(daten: PasswortAendern, response: Response,
                     nutzer: sqlite3.Row = Depends(angemeldet),
                     conn: sqlite3.Connection = Depends(hole_db),
                     cfg: Einstellungen = Depends(hole_cfg)):
    if nutzer["rolle"] == "superadmin":
        raise HTTPException(400, "Das Passwort des Superadmins wird in der .env festgelegt.")
    if not passwort_pruefen(daten.alt, nutzer["passwort_hash"]):
        raise HTTPException(400, "Das bisherige Passwort stimmt nicht.")
    _passwort_oder_fehler(daten.neu, daten.neu2)
    with conn:
        conn.execute(
            "UPDATE nutzer SET passwort_hash = ?, sitzungs_stand = sitzungs_stand + 1 WHERE id = ?",
            (passwort_hash(daten.neu, cfg.bcrypt_runden), nutzer["id"]),
        )
    # Andere Geräte werden abgemeldet, dieses bleibt angemeldet.
    setze_session(response, cfg, nutzer["id"], nutzer["sitzungs_stand"] + 1)
    return {"ok": True, "meldung": "Passwort geändert. Andere Geräte sind jetzt abgemeldet."}


class EinstellungDaten(BaseModel):
    h_system: str
    vorzeichen: str
    klang: str
    tagesziel_min: int
    toleranz_cent: int


ERLAUBT = {
    "h_system": ("H", "B"),
    "vorzeichen": ("silben", "zeichen"),
    "klang": ("synth", "klavier"),
    "toleranz_cent": (15, 25, 40),
}


@router.post("/konto/einstellungen")
def einstellungen_speichern(daten: EinstellungDaten,
                            nutzer: sqlite3.Row = Depends(angemeldet),
                            conn: sqlite3.Connection = Depends(hole_db)):
    for feld, werte in ERLAUBT.items():
        if getattr(daten, feld) not in werte:
            raise HTTPException(400, f"Ungültiger Wert für {feld}.")
    if not 1 <= daten.tagesziel_min <= 120:
        raise HTTPException(400, "Das Tagesziel muss zwischen 1 und 120 Minuten liegen.")
    with conn:
        einstellung_sicherstellen(conn, nutzer["id"])
        conn.execute(
            "UPDATE einstellung SET h_system = ?, vorzeichen = ?, klang = ?, tagesziel_min = ?, "
            "toleranz_cent = ? WHERE nutzer_id = ?",
            (daten.h_system, daten.vorzeichen, daten.klang, daten.tagesziel_min,
             daten.toleranz_cent, nutzer["id"]),
        )
    return {"ok": True, "meldung": "Gespeichert."}
