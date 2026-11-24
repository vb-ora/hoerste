"""Admin: Einladungen, Nutzer aktivieren/deaktivieren, Passwort-Links, Rollen.

Admins sehen hier nur Kontodaten, nie Übungsdaten.
"""

from __future__ import annotations

import sqlite3
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from app.auth import (
    darf_rolle_aendern,
    darf_verwalten,
    hole_cfg,
    hole_db,
    neues_token,
    nur_admin,
    nur_superadmin,
    schreibschutz,
)
from app.config import Einstellungen
from app.db import iso, jetzt

router = APIRouter(prefix="/api/admin", dependencies=[Depends(schreibschutz)])


def _link(request: Request, pfad: str) -> str:
    return str(request.base_url).rstrip("/") + pfad


def _ziel(conn: sqlite3.Connection, nutzer_id: int) -> sqlite3.Row:
    zeile = conn.execute("SELECT * FROM nutzer WHERE id = ?", (nutzer_id,)).fetchone()
    if not zeile:
        raise HTTPException(404, "Konto nicht gefunden.")
    return zeile


@router.post("/einladungen")
def einladung_erstellen(request: Request, admin: sqlite3.Row = Depends(nur_admin),
                        conn: sqlite3.Connection = Depends(hole_db),
                        cfg: Einstellungen = Depends(hole_cfg)):
    klar, gehasht = neues_token()
    gueltig_bis = jetzt() + timedelta(days=cfg.einladung_tage)
    with conn:
        conn.execute(
            "INSERT INTO einladung (token, erstellt_von, gueltig_bis) VALUES (?, ?, ?)",
            (gehasht, admin["id"], iso(gueltig_bis)),
        )
    return {"ok": True, "link": _link(request, f"/einladung/{klar}"), "tage": cfg.einladung_tage}


@router.post("/einladungen/{einladung_id}/zurueckziehen")
def einladung_zurueckziehen(einladung_id: int, _admin: sqlite3.Row = Depends(nur_admin),
                            conn: sqlite3.Connection = Depends(hole_db)):
    with conn:
        geaendert = conn.execute(
            "UPDATE einladung SET aktiv = 0 WHERE id = ? AND eingeloest_am IS NULL", (einladung_id,)
        ).rowcount
    if not geaendert:
        raise HTTPException(404, "Einladung nicht gefunden.")
    return {"ok": True}


class AktivDaten(BaseModel):
    aktiv: bool


@router.post("/nutzer/{nutzer_id}/aktiv")
def nutzer_aktiv(nutzer_id: int, daten: AktivDaten, admin: sqlite3.Row = Depends(nur_admin),
                 conn: sqlite3.Connection = Depends(hole_db)):
    ziel = _ziel(conn, nutzer_id)
    if not darf_verwalten(admin, ziel):
        raise HTTPException(403, "Dieses Konto darfst du nicht ändern.")
    with conn:
        if daten.aktiv:
            conn.execute("UPDATE nutzer SET aktiv = 1 WHERE id = ?", (nutzer_id,))
        else:
            conn.execute(
                "UPDATE nutzer SET aktiv = 0, sitzungs_stand = sitzungs_stand + 1 WHERE id = ?",
                (nutzer_id,),
            )
            conn.execute(
                "UPDATE passwort_link SET aktiv = 0 WHERE nutzer_id = ? AND eingeloest_am IS NULL",
                (nutzer_id,),
            )
    return {"ok": True}


@router.post("/nutzer/{nutzer_id}/passwort-link")
def passwort_link_erstellen(nutzer_id: int, request: Request, admin: sqlite3.Row = Depends(nur_admin),
                            conn: sqlite3.Connection = Depends(hole_db),
                            cfg: Einstellungen = Depends(hole_cfg)):
    ziel = _ziel(conn, nutzer_id)
    if not darf_verwalten(admin, ziel):
        raise HTTPException(403, "Dieses Konto darfst du nicht ändern.")
    if not ziel["aktiv"]:
        raise HTTPException(400, "Das Konto ist deaktiviert. Erst wieder aktivieren.")
    klar, gehasht = neues_token()
    gueltig_bis = jetzt() + timedelta(hours=cfg.passwort_link_stunden)
    with conn:
        # Ältere offene Links für dieses Konto verfallen.
        conn.execute(
            "UPDATE passwort_link SET aktiv = 0 WHERE nutzer_id = ? AND eingeloest_am IS NULL",
            (nutzer_id,),
        )
        conn.execute(
            "INSERT INTO passwort_link (nutzer_id, token, erstellt_von, gueltig_bis) VALUES (?, ?, ?, ?)",
            (nutzer_id, gehasht, admin["id"], iso(gueltig_bis)),
        )
    return {"ok": True, "link": _link(request, f"/passwort/{klar}"),
            "stunden": cfg.passwort_link_stunden, "name": ziel["name"]}


class RolleDaten(BaseModel):
    rolle: str


@router.post("/nutzer/{nutzer_id}/rolle")
def rolle_setzen(nutzer_id: int, daten: RolleDaten, chef: sqlite3.Row = Depends(nur_superadmin),
                 conn: sqlite3.Connection = Depends(hole_db)):
    if daten.rolle not in ("admin", "nutzer"):
        raise HTTPException(400, "Erlaubt sind nur die Rollen Admin und Nutzer.")
    ziel = _ziel(conn, nutzer_id)
    if not darf_rolle_aendern(chef, ziel):
        raise HTTPException(403, "Die Rolle dieses Kontos lässt sich nicht ändern.")
    with conn:
        conn.execute("UPDATE nutzer SET rolle = ? WHERE id = ?", (daten.rolle, nutzer_id))
    return {"ok": True}
