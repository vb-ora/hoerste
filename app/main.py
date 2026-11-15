"""FastAPI-App Hörste.

Etappe 0: nur /healthz und die Testseite /labor. Datenbank, Backup und
Superadmin kommen in Etappe 1 in den Lifespan.
"""

from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.routes import seiten

BASIS = Path(__file__).parent

app = FastAPI(title="Hörste", docs_url=None, redoc_url=None, openapi_url=None)
app.mount("/static", StaticFiles(directory=BASIS / "static"), name="static")
app.include_router(seiten.router)
