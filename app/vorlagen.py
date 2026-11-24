"""Gemeinsame Jinja2-Umgebung."""

from pathlib import Path

from fastapi.templating import Jinja2Templates

from app.db import aus_iso

templates = Jinja2Templates(directory=Path(__file__).parent / "templates")

ROLLEN_NAMEN = {"superadmin": "Superadmin", "admin": "Admin", "nutzer": "Nutzer"}


def ortszeit(text: str | None, format: str = "%d.%m.%Y %H:%M") -> str:
    """UTC-Zeitstempel aus der DB in Ortszeit (Container: TZ=Europe/Berlin)."""
    if not text:
        return "–"
    return aus_iso(text).astimezone().strftime(format)


templates.env.filters["ortszeit"] = ortszeit
templates.env.globals["ROLLEN_NAMEN"] = ROLLEN_NAMEN
