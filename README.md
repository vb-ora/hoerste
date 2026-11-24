# Hörste

Gehörtraining und Singtraining im Browser – für Handy und Rechner, selbst gehostet auf der Synology.

- Konzept: [docs/KONZEPT.md](docs/KONZEPT.md)
- Etappen: [docs/ETAPPEN.md](docs/ETAPPEN.md)
- Regeln für Claude Code: [CLAUDE.md](CLAUDE.md)

## Einrichtung auf der NAS
1. Repo nach `/volume1/docker/hoerste` klonen
2. `.env.example` nach `.env` kopieren und ausfüllen (`$` im Hash verdoppeln)
3. `mkdir -p data && chmod -R 777 data`
4. `sudo docker compose up --build -d`
5. DSM → Anmeldeportal → Reverse Proxy: `https://hoerste.bora-emby.synology.me:443` → `http://localhost:8020`
   (Zertifikat: Wildcard `*.bora-emby.synology.me`)
   - Reverse-Proxy-Regel → „Benutzerdefinierte Kopfzeile“ → „Erstellen“ → „WebSocket“ (schadet nicht, später nützlich)
   - Zertifikat unter „Sicherheit → Zertifikat → Einstellungen“ der Subdomain zuweisen
   - Router: nur 443 auf die NAS weiterleiten, **nicht** Port 8020
6. Prüfen: `https://hoerste.bora-emby.synology.me/healthz` liefert `{"status":"ok"}`, danach unter `/login` anmelden

### Pflichtwerte in `.env` (ab Etappe 1)
- `HOERSTE_SECRET_KEY`: mindestens 32 Zeichen, z. B. `python3 -c "import secrets; print(secrets.token_urlsafe(48))"`
- `HOERSTE_SUPERADMIN_NAME` und `HOERSTE_SUPERADMIN_PASSWORT_HASH` (bcrypt, jedes `$` als `$$`)
  Hash auf der NAS erzeugen (fragt das Passwort verdeckt ab), danach jedes `$` verdoppeln:
  ```bash
  sudo docker run --rm -it python:3.12-slim sh -c 'pip -q install bcrypt && python -c "import bcrypt,getpass; print(bcrypt.hashpw(getpass.getpass().encode(), bcrypt.gensalt()).decode())"'
  ```
- `HOERSTE_COOKIE_SECURE=true`

Fehlt einer der Werte, startet der Container nicht (`sudo docker logs hoerste` zeigt den Grund).
Beim Start wird die Datenbank nach `data/backups/` gesichert (die letzten 10 bleiben).

## Lokal entwickeln
`.env` im Projektordner anlegen wie oben, aber mit `HOERSTE_COOKIE_SECURE=false` und `HOERSTE_DATA_DIR=./data`.
Die App liest die `.env` selbst ein, ein `set ...` ist nicht nötig.

## Update
```bash
cd /volume1/docker/hoerste && git pull && sudo docker compose up --build -d
```

## Lizenzen Dritter
- pitchy (MIT, Ian Johnson) – Tonhöhenerkennung
- fft.js (MIT, Fedor Indutny) – FFT, von pitchy benötigt
- Salamander Grand Piano (CC-BY 3.0, Alexander Holm) – Klavierklänge
