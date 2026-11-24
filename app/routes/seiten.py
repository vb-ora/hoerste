"""HTML-Seiten und Healthcheck.

Ohne Login erreichbar: /healthz, /login, /einladung/{token}, /passwort/{token}.
Alle anderen Seiten verlangen eine Anmeldung.
"""

from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from app.auth import (
    aktueller_nutzer,
    angemeldet,
    darf_rolle_aendern,
    darf_verwalten,
    hole_db,
    nur_admin,
    sicheres_ziel,
)
from app.routes.api_konto import einladung_finden, passwort_link_finden
from app.vorlagen import templates

router = APIRouter()


def _seite(request: Request, vorlage: str, titel: str, nutzer, **daten):
    return templates.TemplateResponse(request, vorlage, {"titel": titel, "nutzer": nutzer, **daten})


def _hinweis(request: Request, titel: str, text: str, status: int = 200):
    return templates.TemplateResponse(
        request, "hinweis.html", {"titel": titel, "text": text, "nutzer": None}, status_code=status
    )


@router.get("/healthz")
def healthz() -> dict:
    return {"status": "ok"}


@router.get("/favicon.ico", include_in_schema=False)
def favicon():
    return RedirectResponse("/static/img/logo.svg", status_code=301)


# ---------- ohne Login ----------

@router.get("/login", response_class=HTMLResponse)
def login_seite(request: Request, weiter: str | None = None,
                nutzer: sqlite3.Row | None = Depends(aktueller_nutzer)):
    if nutzer:
        return RedirectResponse(sicheres_ziel(weiter), status_code=303)
    return _seite(request, "login.html", "Anmelden", None, weiter=sicheres_ziel(weiter))


@router.get("/einladung/{token}", response_class=HTMLResponse)
def einladung_seite(token: str, request: Request, conn: sqlite3.Connection = Depends(hole_db)):
    if not einladung_finden(conn, token):
        return _hinweis(request, "Einladung ungültig",
                        "Diese Einladung ist abgelaufen oder wurde schon benutzt. "
                        "Bitte frag nach einem neuen Link.", 410)
    return _seite(request, "einladung.html", "Konto anlegen", None, token=token)


@router.get("/passwort/{token}", response_class=HTMLResponse)
def passwort_seite(token: str, request: Request, conn: sqlite3.Connection = Depends(hole_db)):
    link = passwort_link_finden(conn, token)
    if not link:
        return _hinweis(request, "Link ungültig",
                        "Dieser Link ist abgelaufen oder wurde schon benutzt. "
                        "Bitte frag nach einem neuen Link.", 410)
    return _seite(request, "passwort.html", "Neues Passwort", None, token=token, name=link["nutzer_name"])


# ---------- mit Login ----------

@router.get("/", response_class=HTMLResponse)
def start(request: Request, nutzer: sqlite3.Row = Depends(angemeldet)):
    return _seite(request, "start.html", "Start", nutzer)


@router.get("/labor", response_class=HTMLResponse)
def labor(request: Request, nutzer: sqlite3.Row = Depends(angemeldet)):
    return _seite(request, "labor.html", "Labor", nutzer)


@router.get("/einstellungen", response_class=HTMLResponse)
def einstellungen(request: Request, nutzer: sqlite3.Row = Depends(angemeldet),
                  conn: sqlite3.Connection = Depends(hole_db)):
    einst = conn.execute("SELECT * FROM einstellung WHERE nutzer_id = ?", (nutzer["id"],)).fetchone()
    if einst is None:
        einst = {"h_system": "H", "vorzeichen": "silben", "klang": "synth",
                 "tagesziel_min": 5, "toleranz_cent": 25}
    return _seite(request, "einstellungen.html", "Einstellungen", nutzer, einst=einst)


@router.get("/admin", response_class=HTMLResponse)
def admin(request: Request, nutzer: sqlite3.Row = Depends(nur_admin),
          conn: sqlite3.Connection = Depends(hole_db)):
    konten = conn.execute(
        "SELECT id, name, rolle, aktiv, letzter_login, erstellt_am, sitzungs_stand FROM nutzer "
        "ORDER BY CASE rolle WHEN 'superadmin' THEN 0 WHEN 'admin' THEN 1 ELSE 2 END, name"
    ).fetchall()
    liste = [
        {
            "k": k,
            "verwalten": darf_verwalten(nutzer, k),
            "rolle_aendern": darf_rolle_aendern(nutzer, k),
        }
        for k in konten
    ]
    einladungen = conn.execute(
        "SELECT e.id, e.erstellt_am, e.gueltig_bis, n.name AS von FROM einladung e "
        "LEFT JOIN nutzer n ON n.id = e.erstellt_von "
        "WHERE e.aktiv = 1 AND e.eingeloest_am IS NULL "
        "AND e.gueltig_bis > strftime('%Y-%m-%dT%H:%M:%SZ', 'now') ORDER BY e.erstellt_am DESC"
    ).fetchall()
    return _seite(request, "admin.html", "Verwaltung", nutzer, konten=liste, einladungen=einladungen)
