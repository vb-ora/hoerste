"""Einstellungen aus Umgebungsvariablen (HOERSTE_*).

Lokal wird zusätzlich eine vorhandene `.env` im Projektordner gelesen
(eigener kleiner Parser, keine Abhängigkeit). Echte Umgebungsvariablen haben
Vorrang. Wie bei Docker Compose wird `$$` in der `.env` zu `$`.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

PROJEKT = Path(__file__).resolve().parent.parent


class KonfigFehler(RuntimeError):
    pass


@dataclass(frozen=True)
class Einstellungen:
    daten_dir: Path
    secret_key: str
    superadmin_name: str
    superadmin_hash: str
    cookie_secure: bool = True
    backups_behalten: int = 10
    einladung_tage: int = 7
    passwort_link_stunden: int = 24
    bcrypt_runden: int = 12

    @property
    def db_pfad(self) -> Path:
        return self.daten_dir / "hoerste.db"

    @property
    def backup_dir(self) -> Path:
        return self.daten_dir / "backups"


def lies_env_datei(pfad: Path) -> dict[str, str]:
    werte: dict[str, str] = {}
    if not pfad.is_file():
        return werte
    for zeile in pfad.read_text(encoding="utf-8").splitlines():
        zeile = zeile.strip()
        if not zeile or zeile.startswith("#") or "=" not in zeile:
            continue
        schluessel, wert = zeile.split("=", 1)
        wert = wert.strip()
        if len(wert) >= 2 and wert[0] == wert[-1] and wert[0] in "\"'":
            wert = wert[1:-1]
        werte[schluessel.strip()] = wert.replace("$$", "$")
    return werte


def _wahr(wert: str) -> bool:
    return wert.strip().lower() in ("1", "true", "ja", "yes", "on")


def lade_einstellungen(env_datei: Path | None = PROJEKT / ".env") -> Einstellungen:
    quelle = lies_env_datei(env_datei) if env_datei else {}
    quelle.update({k: v for k, v in os.environ.items() if k.startswith("HOERSTE_")})

    def hole(name: str, standard: str | None = None) -> str:
        wert = quelle.get(f"HOERSTE_{name}", standard)
        if wert is None or wert == "":
            raise KonfigFehler(f"HOERSTE_{name} fehlt (siehe .env.example)")
        return wert

    secret = hole("SECRET_KEY")
    if secret == "bitte-ersetzen" or len(secret) < 32:
        raise KonfigFehler("HOERSTE_SECRET_KEY ist nicht gesetzt oder zu kurz (mindestens 32 Zeichen)")
    pw_hash = hole("SUPERADMIN_PASSWORT_HASH")
    if not pw_hash.startswith("$2") or "bitte-ersetzen" in pw_hash:
        raise KonfigFehler("HOERSTE_SUPERADMIN_PASSWORT_HASH ist kein bcrypt-Hash")

    return Einstellungen(
        daten_dir=Path(hole("DATA_DIR", "./data")).resolve(),
        secret_key=secret,
        superadmin_name=hole("SUPERADMIN_NAME").strip(),
        superadmin_hash=pw_hash,
        cookie_secure=_wahr(hole("COOKIE_SECURE", "true")),
        backups_behalten=int(hole("BACKUPS_BEHALTEN", "10")),
        einladung_tage=int(hole("EINLADUNG_TAGE", "7")),
    )
