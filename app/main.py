"""FastAPI-App Hörste.

Lifespan: Backup → Migration → Superadmin.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import quote

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from app import db, schema
from app.auth import LoginBremse, LoginNoetig, Verweigert, superadmin_abgleichen
from app.config import Einstellungen, lade_einstellungen
from app.routes import api_admin, api_konto, seiten
from app.vorlagen import templates

BASIS = Path(__file__).parent
log = logging.getLogger("hoerste")


def erstelle_app(cfg: Einstellungen | None = None) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        einst = cfg or lade_einstellungen()
        einst.daten_dir.mkdir(parents=True, exist_ok=True)
        gesichert = db.backup(einst.db_pfad, einst.backup_dir, einst.backups_behalten)
        if gesichert:
            log.info("Backup erstellt: %s", gesichert)
        conn = db.verbinde(einst.db_pfad)
        try:
            conn.execute("PRAGMA journal_mode = WAL")
            schema.migriere(conn)
            superadmin_abgleichen(conn, einst)
        finally:
            conn.close()
        app.state.cfg = einst
        app.state.bremse = LoginBremse()
        yield

    app = FastAPI(title="Hörste", docs_url=None, redoc_url=None, openapi_url=None, lifespan=lifespan)
    app.mount("/static", StaticFiles(directory=BASIS / "static"), name="static")
    app.include_router(seiten.router)
    app.include_router(api_konto.router)
    app.include_router(api_admin.router)

    @app.middleware("http")
    async def statisch_neu_pruefen(request: Request, call_next):
        # Nach einem Update sollen Handys nicht mit alter CSS/JS weiterlaufen:
        # Browser fragt jedes Mal per ETag nach, unverändert kommt nur 304 zurück.
        antwort = await call_next(request)
        if request.url.path.startswith("/static/") and "cache-control" not in antwort.headers:
            antwort.headers["Cache-Control"] = "no-cache"
        return antwort

    @app.exception_handler(LoginNoetig)
    async def login_noetig(request: Request, _exc: LoginNoetig):
        if request.url.path.startswith("/api/"):
            return JSONResponse({"detail": "Bitte zuerst anmelden."}, status_code=401)
        ziel = request.url.path + (f"?{request.url.query}" if request.url.query else "")
        return RedirectResponse(f"/login?weiter={quote(ziel, safe='/')}", status_code=303)

    @app.exception_handler(Verweigert)
    async def verweigert(request: Request, _exc: Verweigert):
        if request.url.path.startswith("/api/"):
            return JSONResponse({"detail": "Dafür fehlen die Rechte."}, status_code=403)
        return templates.TemplateResponse(
            request, "hinweis.html",
            {"titel": "Kein Zugriff", "text": "Für diese Seite fehlen dir die Rechte.", "nutzer": None},
            status_code=403,
        )

    return app


app = erstelle_app()
