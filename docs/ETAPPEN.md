# Hörste – Etappenplan

Jede Etappe endet mit einem **Test durch Bora**. Erst danach beginnt die nächste. Claude Code arbeitet immer nur an einer Etappe.

---

## MVP

### Etappe 0 – Risiko-Prototyp: Audio und Mikrofon auf dem Handy
Ziel: früh prüfen, ob Klang und Tonhöhenerkennung auf iPhone, Android und Desktop über die HTTPS-Subdomain zuverlässig laufen.
- Minimales FastAPI-Gerüst mit `/healthz` und einer Testseite `/labor`
- Synth-Ton per Tippen abspielen (AudioContext-Start auf Nutzergeste)
- Mikrofon an, pitchy-Erkennung, Anzeige Frequenz, Notenname, Cent
- Dockerfile, docker-compose.yml, Reverse-Proxy-Eintrag in DSM
- **Test**: Auf dem Handy über `https://hoerste.bora-emby.synology.me/labor` einen Ton spielen und einen gesungenen Ton sauber erkennen. Latenz subjektiv prüfen, mit und ohne Kopfhörer.

### Etappe 1 – Fundament: DB, Login, Rollen, Einstellungen
- `db.py` mit Startup-Backup (letzte 10), additiver Migration, `CREATE TABLE IF NOT EXISTS`
- Tabellen `nutzer`, `einladung`, `einstellung`
- Superadmin aus `.env`, Login und Logout, Session-Cookie, Login-Bremse
- Einladungslinks, Admin-Seite (Nutzer, Rollen, deaktivieren, Passwort zurücksetzen)
- Einstellungsseite: H/B, Silben/Zeichen, Klang, Tagesziel, Toleranz
- Grundlayout, `stil.css`, eigenes schlichtes Logo „Hörste“
- **Test**: Einladung an ein zweites Testkonto, Login von unterwegs, Rollenrechte prüfen

### Etappe 2 – Musiktheorie-Kern und Audio-Engine
- `app/musik/theorie.py`: MIDI ↔ Frequenz, Intervalle, Akkordformeln, Skalen, Stufen
- `app/musik/notation.py` und `static/js/notation.js` mit identischer Ausgabe (Tabellen-Tests)
- `static/js/audio/`: Engine, Synth, Klavier-Sampler (Salamander, C2–C6), Vorladen, Lautstärke
- Hörprobe in `/labor`: Töne, Intervalle, Akkorde in beiden Klängen
- pytest für Theorie und Notation
- **Test**: Klavier klingt auf dem Handy sauber, keine Knackser, Notennamen in allen 4 Kombinationen korrekt

### Etappe 3 – Lernlogik und die ersten zwei Trainer
- `app/lernen/katalog.py`: Trainer 1 (Tonhöhe) und Trainer 2 (Intervalle) mit Lektionen, Items, Learn-Karten (eigene Texte)
- `app/lernen/leitner.py`: Boxen, Fälligkeit, Gewichtung, Aufstiegs-Sperre pro Tag
- `app/lernen/fragen.py`: Fragegenerator je Trainer
- Tabellen `lektion_status`, `item_status`, `sitzung`, `frage`
- Drill-UI: Abspielen, Wiederholen, Antwortauswahl, Rückmeldung (richtig/falsch, Lösung nachhören)
- Seite „Mein Lernstand“ mit Boxen und Verwechslungen
- pytest für Leitner und Fragegenerator
- **Test**: Eine Woche täglich üben, prüfen ob die Auswahl sich „richtig“ anfühlt

### Etappe 4 – Singen-Basis
- Live-Anzeige: Notenname, Cent-Zeiger, Verlaufskurve (Canvas)
- Stimmtest (Umfang, Stimmlage-Vorschlag), Tabelle `stimmtest`
- Übung „Zielton nachsingen“, Tabelle `sing_versuch`
- `app/singen/bewertung.py` mit pytest (synthetische Messreihen)
- **Test**: Tenor-Umfang ermitteln, 20 Zieltöne singen, Werte plausibel?

**→ MVP fertig**

---

## Ausbau

### Etappe 5 – Statistik, Tagesziel, Serie, erste Abzeichen
- Startseite mit Tagesziel-Ring und Serie (nur Anzeige, keine Erinnerung)
- `/statistik`: Übungen pro Woche, Trefferquote pro Trainer, Singen-Verlauf
- `app/abzeichen.py` mit den ersten Abzeichen (Erster Ton, Dranbleiben, Fleißig, Vermessen)

### Etappe 6 – Trainer 3: Akkorde
### Etappe 7 – Trainer 4: Skalen und Modi
### Etappe 8 – Trainer 5: Akkordfolgen (Antwortmodus A, funktional, Stimmführung)

### Etappe 9 – Einstufungstest je Trainer

### Etappe 10 – Singen-Ausbau
- Ton halten (Stabilität), Intervall singen, Tonleiter singen
- Abzeichen Punktlandung und Fels in der Brandung

### Etappe 11 – Medaillen, Feinschliff, Homescreen
- Medaillen je Trainer, SVG-Plaketten
- Web-App-Manifest und Icons für „Zum Home-Bildschirm“ (ohne Push)
- Eigene Merkhilfen pro Intervall
- Bedienung am Desktop verbessern (Tastaturkürzel: Leertaste = abspielen, 1–9 = Antwort)

### Ideen danach
- Trainer „Stufen im Tonartkontext“
- Akkordfolgen Antwortmodus B (Akkord für Akkord)
- Übung „Akkordton singen“ (Terz/Quinte zum Akkord)
- Gezieltes Verwechslungs-Training (nur die zwei verwechselten Items gegeneinander)
- Datenexport pro Nutzer (JSON)
