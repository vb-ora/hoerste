"""Tabellen und Spaltenergänzungen.

Nur additiv: neue Tabellen mit CREATE TABLE IF NOT EXISTS, neue Spalten über
SPALTEN (wird mit PRAGMA table_info geprüft). Nichts umbenennen, nichts löschen.
"""

from __future__ import annotations

import sqlite3

from app.db import spalte_ergaenzen

JETZT_SQL = "(strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))"

TABELLEN = [
    f"""
    CREATE TABLE IF NOT EXISTS nutzer (
        id INTEGER PRIMARY KEY,
        name TEXT NOT NULL UNIQUE COLLATE NOCASE,
        passwort_hash TEXT NOT NULL,
        rolle TEXT NOT NULL DEFAULT 'nutzer',
        letzter_login TEXT,
        erstellt_am TEXT NOT NULL DEFAULT {JETZT_SQL},
        aktiv INTEGER NOT NULL DEFAULT 1
    )
    """,
    f"""
    CREATE TABLE IF NOT EXISTS einladung (
        id INTEGER PRIMARY KEY,
        token TEXT NOT NULL UNIQUE,
        erstellt_von INTEGER REFERENCES nutzer(id),
        gueltig_bis TEXT NOT NULL,
        eingeloest_von INTEGER REFERENCES nutzer(id),
        eingeloest_am TEXT,
        erstellt_am TEXT NOT NULL DEFAULT {JETZT_SQL},
        aktiv INTEGER NOT NULL DEFAULT 1
    )
    """,
    f"""
    CREATE TABLE IF NOT EXISTS einstellung (
        id INTEGER PRIMARY KEY,
        nutzer_id INTEGER NOT NULL UNIQUE REFERENCES nutzer(id),
        h_system TEXT NOT NULL DEFAULT 'H',
        vorzeichen TEXT NOT NULL DEFAULT 'silben',
        klang TEXT NOT NULL DEFAULT 'synth',
        tagesziel_min INTEGER NOT NULL DEFAULT 5,
        toleranz_cent INTEGER NOT NULL DEFAULT 25,
        stimmlage TEXT,
        umfang_tief INTEGER,
        umfang_hoch INTEGER,
        erstellt_am TEXT NOT NULL DEFAULT {JETZT_SQL},
        aktiv INTEGER NOT NULL DEFAULT 1
    )
    """,
    f"""
    CREATE TABLE IF NOT EXISTS passwort_link (
        id INTEGER PRIMARY KEY,
        nutzer_id INTEGER NOT NULL REFERENCES nutzer(id),
        token TEXT NOT NULL UNIQUE,
        erstellt_von INTEGER REFERENCES nutzer(id),
        gueltig_bis TEXT NOT NULL,
        eingeloest_am TEXT,
        erstellt_am TEXT NOT NULL DEFAULT {JETZT_SQL},
        aktiv INTEGER NOT NULL DEFAULT 1
    )
    """,
]

# (tabelle, spalte, definition) – später hinzugekommene Spalten
SPALTEN = [
    # Wird bei Passwortwechsel und Deaktivierung erhöht und macht alte Session-Cookies ungültig.
    ("nutzer", "sitzungs_stand", "INTEGER NOT NULL DEFAULT 0"),
]


def migriere(conn: sqlite3.Connection) -> None:
    with conn:
        for sql in TABELLEN:
            conn.execute(sql)
        for tabelle, spalte, definition in SPALTEN:
            spalte_ergaenzen(conn, tabelle, spalte, definition)
