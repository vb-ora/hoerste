"""SQLite-Verbindung, Startup-Backup und Migrationshelfer.

Schutzregeln (siehe CLAUDE.md): nichts löschen, nur additive Schemaänderungen,
Löschen heißt aktiv = 0. tests/test_migration.py prüft das im Code.
"""

from __future__ import annotations

import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

ZEITFORMAT = "%Y-%m-%dT%H:%M:%SZ"
_NAME = re.compile(r"^[a-z_][a-z0-9_]*$")


def jetzt() -> datetime:
    return datetime.now(timezone.utc)


def iso(zeit: datetime) -> str:
    return zeit.astimezone(timezone.utc).strftime(ZEITFORMAT)


def aus_iso(text: str) -> datetime:
    return datetime.strptime(text, ZEITFORMAT).replace(tzinfo=timezone.utc)


def verbinde(pfad: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(pfad, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 10000")
    return conn


def backup(db_pfad: Path, backup_dir: Path, behalten: int, zeit: datetime | None = None) -> Path | None:
    """Kopiert die DB nach backups/hoerste_YYYYMMDD_HHMMSS.db und behält die neuesten `behalten`."""
    if not db_pfad.is_file():
        return None
    backup_dir.mkdir(parents=True, exist_ok=True)
    stempel = (zeit or datetime.now()).strftime("%Y%m%d_%H%M%S")
    ziel = backup_dir / f"hoerste_{stempel}.db"
    quelle = sqlite3.connect(db_pfad)
    try:
        kopie = sqlite3.connect(ziel)
        try:
            quelle.backup(kopie)
        finally:
            kopie.close()
    finally:
        quelle.close()
    alte = sorted(backup_dir.glob("hoerste_*.db"))
    for datei in alte[: max(0, len(alte) - behalten)]:
        datei.unlink()  # nur Backup-Dateien, nie Inhalte der Datenbank
    return ziel


def spalten(conn: sqlite3.Connection, tabelle: str) -> set[str]:
    if not _NAME.match(tabelle):
        raise ValueError(tabelle)
    return {zeile["name"] for zeile in conn.execute(f"PRAGMA table_info({tabelle})")}


def spalte_ergaenzen(conn: sqlite3.Connection, tabelle: str, spalte: str, definition: str) -> bool:
    """Fügt eine Spalte hinzu, falls sie fehlt. Gibt True zurück, wenn ergänzt wurde."""
    if not _NAME.match(spalte):
        raise ValueError(spalte)
    if spalte in spalten(conn, tabelle):
        return False
    conn.execute(f"ALTER TABLE {tabelle} ADD COLUMN {spalte} {definition}")
    return True
