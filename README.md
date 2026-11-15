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
6. Prüfen: `https://hoerste.bora-emby.synology.me/healthz` liefert `{"status":"ok"}`, Testseite unter `/labor`

Hinweis Etappe 0: Die App braucht noch keine Werte aus `.env`, die Datei muss aber existieren (sonst bricht `docker compose` ab).

## Update
```bash
cd /volume1/docker/hoerste && git pull && sudo docker compose up --build -d
```

## Lizenzen Dritter
- pitchy (MIT, Ian Johnson) – Tonhöhenerkennung
- fft.js (MIT, Fedor Indutny) – FFT, von pitchy benötigt
- Salamander Grand Piano (CC-BY 3.0, Alexander Holm) – Klavierklänge
