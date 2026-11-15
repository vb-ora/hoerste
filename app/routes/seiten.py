"""HTML-Seiten und Healthcheck."""

from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

router = APIRouter()
templates = Jinja2Templates(directory=Path(__file__).parent.parent / "templates")


@router.get("/healthz")
def healthz() -> dict:
    return {"status": "ok"}


# Etappe 0: /labor ist noch ohne Login erreichbar, weil es Login erst ab
# Etappe 1 gibt. Ab Etappe 1 verlangt auch /labor eine Anmeldung.
@router.get("/labor", response_class=HTMLResponse)
def labor(request: Request):
    return templates.TemplateResponse(request, "labor.html", {"titel": "Labor"})
