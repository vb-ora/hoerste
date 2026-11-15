# CLAUDE.md – Hörste

Web-App für Gehörtraining und Singtraining. Oberflächenname **Hörste**, technischer Name überall **hoerste** (Paket, Container, DB-Datei, Env-Variablen, Cookies).

Vor jeder Arbeit lesen: `docs/KONZEPT.md` (Architektur, Datenmodell, Lernlogik) und `docs/ETAPPEN.md` (aktueller Plan).

## Stack
- Python 3.12, FastAPI, Uvicorn, Jinja2, SQLite (Standardbibliothek `sqlite3`), bcrypt, itsdangerous
- Frontend: Jinja2-Templates + Vanilla-JS (ES Modules), **kein Build-Schritt, kein npm, kein CDN**
- Mitgelieferte Fremdbibliotheken nur unter `app/static/js/vendor/` mit Lizenzdatei (pitchy und dessen Abhängigkeit fft.js, beide MIT; Herkunft und Anpassungen in `vendor/LIESMICH.txt`)
- Klavier-Samples unter `app/static/samples/klavier/` mit `LIZENZ.txt` (Salamander Grand Piano, CC-BY 3.0)
- Betrieb: Docker auf Synology DS225+, Reverse Proxy im DSM, `https://hoerste.bora-emby.synology.me`

## Befehle
```bash
# Lokal entwickeln (ohne Docker)
python -m venv .venv && .venv\Scripts\activate      # Windows
pip install -r requirements.txt -r requirements-dev.txt
set HOERSTE_DATA_DIR=./data & set HOERSTE_COOKIE_SECURE=false
uvicorn app.main:app --reload --port 8000

# Tests
pytest -q

# Deployment auf der NAS (macht Bora selbst)
cd /volume1/docker/hoerste && git pull && sudo docker compose up --build -d
```
Hinweis: Mikrofon geht lokal nur über `http://localhost`. Tests auf dem Handy laufen über die HTTPS-Subdomain.

## Projektstruktur
```
app/
  main.py            FastAPI-App, Lifespan: Backup → Migration → Superadmin
  config.py          Einstellungen aus Umgebungsvariablen (HOERSTE_*)
  db.py              Verbindung, Backup, Migrationshelfer
  schema.py          Tabellen (CREATE TABLE IF NOT EXISTS) und Spaltenergänzungen
  auth.py            Passwort-Hash, Session, Rollen, Abhängigkeiten
  abzeichen.py       Abzeichen-Katalog und Vergabe
  musik/theorie.py   MIDI, Intervalle, Akkorde, Skalen, Stufen, Stimmführung
  musik/notation.py  Anzeige-Namen (H/B, Silben/Zeichen, tonartgerecht)
  lernen/katalog.py  Trainer, Lektionen, Items, Learn-Texte
  lernen/leitner.py  Boxen, Fälligkeit, Gewichtung
  lernen/fragen.py   Fragegenerator je Trainer
  singen/bewertung.py Kennzahlen aus Messreihen
  routes/            seiten.py, api_drill.py, api_singen.py, api_statistik.py, api_konto.py, api_admin.py
  templates/         Jinja2
  static/            css/, js/ (audio/, pitch/, vendor/), samples/, img/
tests/               pytest
docs/                KONZEPT.md, ETAPPEN.md
data/                (gitignored) hoerste.db, backups/ – Bind-Mount im Container unter /data
```

## Arbeitsweise
- Immer **nur die aktuelle Etappe** aus `docs/ETAPPEN.md` umsetzen. Am Ende kurz zusammenfassen, was Bora testen soll, und stoppen.
- Bei Unklarheiten fragen statt raten. Keine neuen Abhängigkeiten ohne Rückfrage.
- Git: Committen ist erlaubt, **niemals pushen**. Das macht Bora.
- Änderungen an `docs/KONZEPT.md` nur, wenn eine Entscheidung sich wirklich geändert hat, und im Commit erwähnen.

## Datenbank-Schutzregeln (nicht verhandelbar)
- **Kein `DROP TABLE`, kein `DELETE`, keine nicht-additiven Schemaänderungen.**
- Neue Tabellen nur mit `CREATE TABLE IF NOT EXISTS`.
- Neue Spalten nur per `ALTER TABLE ... ADD COLUMN` nach Prüfung mit `PRAGMA table_info`.
- Löschen heißt `aktiv = 0` (Soft-Delete) in allen Tabellen.
- Beim Start automatisches Backup `data/backups/hoerste_YYYYMMDD_HHMMSS.db`, die letzten 10 bleiben.
- DB-Pfad stabil und absolut: `${HOERSTE_DATA_DIR}/hoerste.db`.
- Keine Spalten umbenennen, keine Constraints nachträglich verschärfen. Lieber eine neue Tabelle.
- Lektionen, Items und Abzeichen leben im Code. In der DB stehen nur stabile Schlüssel. **Schlüssel nie umbenennen**, sonst geht Fortschritt verloren.

## Musikalische Regeln
- Intern ist jeder Ton eine **MIDI-Nummer** (A4 = 69 = 440 Hz). Notennamen entstehen nur in der Anzeige.
- `notation.py` und `static/js/notation.js` müssen identische Ergebnisse liefern. Gemeinsame Testtabelle in `tests/test_notation.py`, die JS-Seite wird gegen dieselbe Tabelle (als JSON exportiert) geprüft.
- In Skalen, Akkorden und Folgen tonartgerecht schreiben (F-Dur → B, nicht Ais).
- Item-Schlüssel nach Schema `trainer:inhalt:darbietung`, z. B. `int:g3:auf`, `ton:fis:mittel`, `akk:moll:gleich`.
- Akkordfolgen funktional: Tonart zufällig, Start auf der Tonika, enge Stimmführung.

## Audio und Mikrofon (Browser)
- `AudioContext` nur nach Nutzergeste erzeugen oder fortsetzen (iOS).
- `getUserMedia({audio: {echoCancellation: false, noiseSuppression: false, autoGainControl: false}})`
- Tonhöhenerkennung ausschließlich im Browser. **Kein Audio an den Server schicken**, nur Messreihen (Zeit, Hz, Klarheit).
- Bewertung der Messreihen in Python (`singen/bewertung.py`), nicht in JS.
- Samples als MP3 (iOS-tauglich), vorladen beim ersten Öffnen eines Trainers mit Klavierklang.

## Sicherheit
- Zugriff von außen ist vorgesehen. Jede Seite außer `/login`, `/einladung/{token}`, `/healthz` und statischen Dateien verlangt Login.
- Session-Cookie `hoerste_session`: HttpOnly, Secure (abschaltbar nur lokal), SameSite=Lax.
- Schreibende API-Aufrufe verlangen Header `X-Hoerste: 1`.
- Login-Bremse: 5 Fehlversuche pro Name und IP → 15 Minuten Sperre.
- Rollen: `superadmin` (aus `.env`, genau einer), `admin`, `nutzer`. Nur der Superadmin ernennt Admins.
- Admins sehen **keine Übungsdaten** anderer Nutzer.
- Keine Secrets im Repo. `.env` ist gitignored.

## Inhalte und Urheberrecht
- **Nichts von Pitch Trainer übernehmen**: keine Texte, Lektionsnamen, Grafiken, Farben, Layouts. Nur eigene Formulierungen und eigenes Design.
- **Keine geschützte Musik** in der App, weder als Audio noch als Noten noch als Liedzitat.
- Merkhilfen nur als Text und nur mit gemeinfreien Volks- und Kinderliedern. Nutzer können eigene Merkhilfen anlegen.

## Oberfläche
- Sprache Deutsch. Generisches Maskulinum, **kein Gendern** (keine Doppelpunkte, Sternchen o. Ä.).
- Mobile first: große Tippflächen, Daumenbedienung, kein Hover-Zwang. Desktop mit derselben Oberfläche.
- **Keine Erinnerungen**: kein Push, keine Benachrichtigungen, keine E-Mails, kein Service Worker für Notifications.
- Learn-Karten kurz: höchstens 30 Sekunden Lesen und Hören.
- Lernlogik transparent: Boxen und Fälligkeiten sind für den Nutzer einsehbar.

## Tests
- Pflicht-Tests: `musik/theorie.py`, `musik/notation.py`, `lernen/leitner.py`, `lernen/fragen.py`, `singen/bewertung.py`.
- Leitner-Tests mit fester Uhrzeit (Zeit als Parameter übergeben, nicht `datetime.now()` im Kern).
- Zufall in Fragegenerator über übergebenen `random.Random(seed)` testbar machen.
