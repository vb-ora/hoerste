# Hörste – Konzept

Web-App für Gehörtraining und Singtraining. Läuft als Docker-Container auf der Synology DS225+, erreichbar unter `https://hoerste.bora-emby.synology.me` (Heimnetz und unterwegs). Name in der Oberfläche: **Hörste**, im Code, in Pfaden, Containern und der Datenbank überall: **hoerste**.

Pitch Trainer dient nur als Orientierung für Funktionsumfang und Lernlogik. Texte, Lektionen, Grafiken und Design sind eigene Entwicklungen.

---

## 1. Architekturentscheidungen

| Thema | Entscheidung | Begründung |
|---|---|---|
| Backend | FastAPI (Python 3.12) | Bewährter Stack aus den anderen Apps |
| Frontend | Jinja2-Seiten + Vanilla-JS-Module (ES Modules), kein Build-Schritt | Drill und Pitch-Anzeige sind stark interaktiv (Audio, Canvas, Timing). HTMX bringt hier wenig. Jinja liefert Seitengerüst und Nutzereinstellungen, JS macht die Interaktion. |
| Datenhaltung | SQLite im Bind-Mount `./data` | Bewährt, einfache Backups |
| Klang | Eigene kleine Audio-Engine auf Web Audio: **Synth** (Dreieck + Tiefpass + Hüllkurve) und **Klavier** (Samples) | Beides wählbar pro Nutzer. Kein Tone.js nötig, weniger Abhängigkeiten. |
| Klavier-Samples | Salamander Grand Piano (CC-BY 3.0, Alexander Holm), MP3, jeder 3. Halbton von C2 bis C6, Zwischentöne per `playbackRate` | Ca. 2–3 MB, MP3 läuft auch auf iOS. Lizenzhinweis in `static/samples/klavier/LIZENZ.txt` und auf der Infoseite. |
| Tonhöhenerkennung | Im Browser mit **pitchy** (McLeod-Methode), lokal mitgeliefert unter `static/js/vendor/` | Geringe Latenz, bei Chorstar erprobt. Kein Audio-Upload zum Server. |
| Bewertung Singen | Browser schickt die Messreihe (Zeit, Frequenz, Klarheit), **Python** berechnet die Kennzahlen | Bewertungslogik ist testbar (pytest) und an einer Stelle |
| Fragenauswahl | Server (Leitner-Logik in Python) | Fortschritt liegt zentral, Logik testbar, Antworten werden serverseitig geprüft |
| Zugriff | DSM-Reverse-Proxy mit Wildcard-Zertifikat, Uvicorn mit `--proxy-headers` | HTTPS ist Pflicht für das Mikrofon. Lokal geht `localhost` ohne HTTPS. |
| Login | Eigene Session-Cookies (signiert), bcrypt, Rollen | Zugriff von außen erfordert echten Login |
| Erinnerungen | **Keine** (kein Push, keine Mails, kein Service Worker für Benachrichtigungen) | Ausdrücklicher Wunsch |

---

## 2. Nutzer und Rollen

| Rolle | Darf |
|---|---|
| `superadmin` | Alles. Genau einer, angelegt aus `.env` beim Start. Ernennt und entzieht Admins. |
| `admin` | Nutzer einladen, deaktivieren, Passwort zurücksetzen. Keine Admins ernennen. |
| `nutzer` | Üben, eigene Statistik, eigene Einstellungen |

- **Einladungslinks**: Admin erzeugt einen Link mit Token (7 Tage gültig, einmal nutzbar). Darüber legt die Person Name und Passwort selbst fest. Keine offene Registrierung.
- **Passwort zurücksetzen**: Admin erzeugt einen Einmal-Link (24 Stunden gültig), über den die Person selbst ein neues Passwort setzt. Der Admin kennt das Passwort nie.
- **Wer verwaltet wen**: Admins verwalten nur Konten mit Rolle `nutzer`. Der Superadmin verwaltet alle außer sich selbst (sein Konto kommt aus der `.env`).
- **Login-Bremse** im Arbeitsspeicher (ein Uvicorn-Prozess). Nach einem Neustart sind die Zähler zurückgesetzt.
- **Datenschutz im Chor**: Admins sehen die Nutzerliste (Name, Rolle, aktiv, letzter Login), aber **keine Übungsdaten** anderer Personen.
- **Sicherheit**: Cookie `HttpOnly`, `Secure`, `SameSite=Lax`, Laufzeit 30 Tage. Login-Bremse: nach 5 Fehlversuchen pro Name und IP 15 Minuten Sperre. API-Aufrufe mit Schreibzugriff verlangen den Header `X-Hoerste: 1` (CSRF-Schutz zusammen mit SameSite). Passwort mindestens 10 Zeichen.

---

## 3. Notation (pro Nutzer einstellbar)

Intern wird **jeder Ton als MIDI-Nummer** gespeichert (A4 = 69 = 440 Hz). Notennamen entstehen nur in der Anzeige (`app/musik/notation.py` und gespiegelt in `static/js/notation.js`).

Zwei unabhängige Schalter:
- **H-System**: `H` (deutsch: H = 11, B = 10) oder `B` (international: B = 11, B♭ = 10)
- **Vorzeichen**: `silben` (Cis, Des, Es …) oder `zeichen` (C♯, D♭, E♭ …)

| Halbton | H + Silben | H + Zeichen | B + Silben | B + Zeichen |
|---|---|---|---|---|
| 1 | Cis / Des | C♯ / D♭ | Cis / Des | C♯ / D♭ |
| 3 | Dis / Es | D♯ / E♭ | Dis / Es | D♯ / E♭ |
| 10 | Ais / B | A♯ / B | Ais / Bes | A♯ / B♭ |
| 11 | H | H | B | B |

- Im **Tonhöhen-Trainer** zeigen schwarze Tasten beide Namen („Cis/Des“).
- In **Skalen, Akkorden und Folgen** wird tonartgerecht geschrieben (F-Dur hat B bzw. B♭, nicht Ais). Die Schreibweise ergibt sich aus Grundton und Struktur, nicht aus einer festen Tabelle.
- Die Kombination „B + Silben“ ist ungewöhnlich (Bes), wird aber konsistent unterstützt.
- Oktavbezeichnung: wissenschaftlich (C4 = eingestrichenes c). Optional später Helmholtz (c′).

---

## 4. Lernlogik (transparent)

### 4.1 Begriffe
- **Trainer**: Tonhöhe, Intervalle, Akkorde, Skalen, Akkordfolgen
- **Lektion**: Gruppe von Lerneinheiten innerhalb eines Trainers. Hat eine Learn-Karte (höchstens 30 Sekunden Lesen und Hören).
- **Lerneinheit (Item)**: das, was abgefragt wird, z. B. `int:g3:auf` = große Terz, melodisch aufwärts. Schlüssel sind stabile Strings und werden in der DB gespeichert.

### 4.2 Leitner-Boxen
Jede Lerneinheit hat pro Nutzer eine Box von 0 bis 5:

| Box | Bedeutung | Wieder fällig nach |
|---|---|---|
| 0 | neu, noch nicht eingeführt | – |
| 1 | gerade gelernt / zuletzt falsch | gleiche Sitzung, dann 1 Tag |
| 2 | wird besser | 2 Tage |
| 3 | sitzt meistens | 4 Tage |
| 4 | sitzt sicher | 8 Tage |
| 5 | gefestigt | 16 Tage |

Regeln:
- **Richtig**: Box + 1. Pro Kalendertag steigt eine Einheit höchstens einmal auf. Massiertes Wiederholen in einer Sitzung zählt also nicht doppelt.
- **Falsch**: Box = max(1, Box − 2). Die Einheit kommt in derselben Sitzung nach 3 bis 5 anderen Fragen noch einmal.
- **Gewichtung bei der Auswahl** (Pool = freigeschaltete Lektionen des Trainers):
  - fällig, Box 1–2: Gewicht 4 („fast sitzt“ kommt am häufigsten)
  - fällig, Box 3: Gewicht 2
  - fällig, Box 4–5: Gewicht 1
  - nicht fällig: Gewicht 0,3 (nur zum Auffüllen)
  - neu (Box 0): höchstens 2 neue Einheiten pro Sitzung, jeweils nach kurzer Vorstellung
- Nie zweimal direkt hintereinander dieselbe Einheit.
- **Lektion abgeschlossen**, wenn alle ihre Einheiten mindestens Box 3 erreicht haben. Dann wird die nächste Lektion frei.

### 4.3 Transparenz
- Seite **„Mein Lernstand“** je Trainer: Tabelle mit Einheit, Box, fällig am, Trefferquote, letzte 5 Antworten (✓/✗).
- **Verwechslungen**: Es wird gespeichert, *was* falsch geantwortet wurde. Die Statistik zeigt die häufigsten Paare (z. B. „große Terz ↔ reine Quarte“, 7×).
- Die Regeln oben stehen in Kurzform auf der Seite („So wählt Hörste deine Fragen aus“).
- Pro Einheit und pro Lektion: „Zurücksetzen“ und „Jetzt gezielt üben“.

### 4.4 Sitzung und Tagesziel
- Eine Drill-Sitzung dauert standardmäßig 20 Fragen oder bis der Nutzer beendet.
- **Tagesziel**: 5 Minuten aktive Übungszeit pro Tag (einstellbar). Pausen über 60 Sekunden zählen nicht.
- **Serie**: Tage in Folge mit erreichtem Tagesziel. Wird nur angezeigt, nie erinnert.

### 4.5 Einstufungstest (Ausbau)
Pro Trainer 12 bis 16 Fragen quer durch alle Lektionen, von leicht nach schwer, Abbruch nach 3 Fehlern in Folge. Richtig beantwortete Einheiten starten in Box 3, ihre Lektionen werden freigeschaltet.

---

## 5. Curriculum-Empfehlung (Recherche zu Frage 8)

**Was übliche Apps machen**: Fast alle Gehörtrainings-Apps trennen bei Intervallen zwischen *melodisch aufwärts*, *melodisch abwärts* und *harmonisch* (gleichzeitig), dazu einen gemischten Modus. Abwärts gilt als schwerer als aufwärts. Empfohlen wird, harmonisch erst zu üben, wenn melodisch sitzt. Bei Akkorden kommen Umkehrungen als eigene Stufe nach der Grundstellung. Akkordfolgen werden in guten Apps **funktional** geübt: Die Tonart wechselt zufällig, man erkennt die Stufen (I, IV, V …) relativ zur Tonika, oft mit einer Kadenz vorweg. Dieser „Tonartkontext“ gilt in der Didaktik als das, was am meisten fürs echte Musizieren bringt.

**Folgerung für Hörste**: Jeder Trainer hat zwei Achsen, *Inhalt* (Lektionen) und *Schwierigkeit der Darbietung*. Die Darbietung wird Teil des Item-Schlüssels, damit die Boxen getrennt geführt werden.

### Trainer 1 – Tonhöhe
- Lektionen: L1 C, E, G → L2 + D, A → L3 + F, H → L4 + Fis, B → L5 + Cis, Es, As (alle 12)
- Darbietung: Oktave mittel → tief/hoch → zufällig
- Option **„mit Bezugston“** (vorher wird ein A oder C gespielt): macht die Aufgabe relativ und ist für den Chor sehr praxisnah. Ohne Bezugston ist es echtes absolutes Hören, das bei Erwachsenen als schwer erlernbar gilt. Beides anbieten, getrennt auswerten.

### Trainer 2 – Intervalle
- Lektionen (klanglich kontrastreich zuerst): L1 Oktave, Quinte, Quarte → L2 + große und kleine Terz → L3 + große und kleine Sekunde → L4 + große und kleine Sexte → L5 + große und kleine Septime, Tritonus
- Darbietung als eigene Stufen: aufwärts → abwärts → harmonisch → gemischt
- Item-Schlüssel z. B. `int:k3:ab` (kleine Terz abwärts)
- Grundton zufällig im angenehmen Bereich, Umfang innerhalb einer Oktave. Dezimen und mehr später optional.

### Trainer 3 – Akkorde
- L1 Dur, Moll (Grundstellung)
- L2 + vermindert, übermäßig
- L3 Dur und Moll in Umkehrungen (gefragt wird nur die Klangart)
- L4 Septakkorde: Dominantsept (7), großer Sept (maj7), Moll-Sept (m7)
- L5 + halbvermindert (m7♭5), vermindert (°7)
- L6 (poprelevant) sus2, sus4, add9
- Darbietung: erst arpeggiert dann gleichzeitig → nur gleichzeitig. Enge Lage, mittlere Lage.
- Später optional eine eigene Frage „Welche Umkehrung?“.

### Trainer 4 – Skalen und Modi
- L1 Dur, natürliches Moll
- L2 + Dur-Pentatonik, Moll-Pentatonik
- L3 + Blues-Skala
- L4 + Dorisch, Mixolydisch (im Pop häufig)
- L5 + Lydisch, Phrygisch
- L6 + harmonisch Moll, melodisch Moll
- Darbietung: aufwärts vom gleichen Grundton → auf- und abwärts → zufälliger Grundton
- Learn-Karten beschreiben den Charakter (z. B. „Dorisch: Moll mit heller Sexte“), immer mit Vergleich zu Dur oder Moll.

### Trainer 5 – Akkordfolgen
- Immer funktional: Tonart zufällig je Frage, Folge beginnt auf der Tonika, Bass klar im Grundton, Oberstimmen mit enger Stimmführung (nahe Umkehrungen statt paralleler Grundstellungen). Das klingt wie echte Begleitung.
- L1 Kadenzen: I–IV–I, I–V–I, I–IV–V–I
- L2 Pop: I–V–vi–IV, I–vi–IV–V
- L3 ii–V–I, I–IV–vi–V
- L4 Moll: i–iv–v–i, i–VI–III–VII
- L5 12-taktiger Blues
- Antwortmodus A (MVP des Trainers): ganze Folge aus 3 bis 5 Optionen wählen
- Antwortmodus B (später): Akkord für Akkord die Stufe antippen
- Anzeige: römische Ziffern, darunter optional die Akkordnamen in der Tonart

### Idee für später: Stufen im Tonartkontext
Kadenz erklingt, dann ein Ton, Frage: welche Stufe (1 bis 7)? Gerade für Chorsänger nützlich, um Einsätze aus der Begleitung zu finden.

### Merkhilfen
Nur als **Textidee** in Learn-Karten, ohne Tonbeispiel, und nur mit gemeinfreien Volks- und Kinderliedern, z. B.:
- große Sekunde aufwärts: „Alle meine Entchen“
- kleine Terz abwärts: „Kuckuck, Kuckuck“
- reine Quarte aufwärts: „O Tannenbaum“
- reine Quinte aufwärts: „Morgen kommt der Weihnachtsmann“ (nach den ersten beiden gleichen Tönen)

Zusätzlich kann jeder Nutzer **eigene Merkhilfen** als Text pro Intervall hinterlegen. Keine geschützte Musik in der App, weder als Ton noch als Text-Zitat.

---

## 6. Singen

### 6.1 Tonhöhenerkennung (Browser)
- `getUserMedia` mit `echoCancellation: false`, `noiseSuppression: false`, `autoGainControl: false` (sonst verfälscht der Browser die Tonhöhe)
- `AnalyserNode`, Fenster 2048 Samples, Auswertung per `requestAnimationFrame` mit pitchy
- Filter: Klarheit ≥ 0,9, Lautstärke-Schwelle (RMS), Median über 5 Werte, Frequenzbereich 60 bis 1200 Hz
- Anzeige: Notenname (nach Nutzereinstellung), Abweichung in Cent (Zeiger ±50), Verlaufskurve auf Canvas mit Zielton-Band
- `AudioContext` erst nach Tippen starten (iOS-Pflicht). Hinweis: Mit Kopfhörern üben, wenn ein Bezugston mitläuft.

### 6.2 Stimmtest
- Tiefsten und höchsten **bequemen** Ton jeweils 1 Sekunde halten, zweimal messen
- Speichert `umfang_tief` und `umfang_hoch` (MIDI). Vorschlag der Stimmlage nach Lage des Umfangs (Bass, Bariton, Tenor, Alt, Mezzosopran, Sopran), manuell überschreibbar. Angabe „Tenor“ ist für Bora voreingestellt.
- Alle Singübungen bleiben innerhalb des Umfangs mit einem Halbton Sicherheitsabstand.
- Gespielte Bezugstöne liegen in der gesungenen Oktave des Nutzers.

### 6.3 Übungen
| Übung | Ablauf | MVP |
|---|---|---|
| Zielton nachsingen | Ton erklingt, nachsingen, 2 s Messung | ja |
| Ton halten | Ton 5 s halten, Bewertung der Stabilität | Ausbau |
| Intervall singen | Grundton erklingt, Intervall wird angezeigt, Zielton singen | Ausbau |
| Tonleiter singen | Grundton erklingt, Tonleiter Ton für Ton, Bewertung je Stufe | Ausbau |
| Akkordton singen (Idee) | Akkord erklingt, Terz oder Quinte dazu singen | später |

### 6.4 Bewertung (`app/singen/bewertung.py`)
- **Einschwingzeit**: bis die Tonhöhe erstmals 300 ms am Stück innerhalb ±50 Cent liegt
- **Abweichung**: Median der Cent-Werte nach dem Einschwingen
- **Stabilität**: Standardabweichung der Cent-Werte nach dem Einschwingen
- **Treffer**: |Abweichung| ≤ Toleranz (Standard 25 Cent, wählbar 15, 25 oder 40)
- **Oktavfehler** (um ±1200 Cent daneben) werden eigens erkannt. Option „Oktave egal“ für Kinder und Frauenstimmen bei tiefen Bezugstönen.
- Gespeichert werden die Kennzahlen und eine auf 50 ms ausgedünnte Kurve (JSON) für die spätere Anzeige.

---

## 7. Datenmodell (SQLite)

Alle Tabellen mit `id INTEGER PRIMARY KEY`, `erstellt_am`, `aktiv INTEGER DEFAULT 1` (Soft-Delete).

| Tabelle | Wichtige Spalten |
|---|---|
| `nutzer` | `name` (unique, ohne Groß-/Kleinschreibung), `passwort_hash`, `rolle`, `letzter_login`, `sitzungs_stand` (erhöht bei Passwortwechsel/Deaktivierung, macht alte Cookies ungültig) |
| `einladung` | `token` (als SHA-256-Hash), `erstellt_von`, `gueltig_bis`, `eingeloest_von`, `eingeloest_am` |
| `passwort_link` | `nutzer_id`, `token` (Hash), `erstellt_von`, `gueltig_bis` (24 h), `eingeloest_am` |
| `einstellung` | `nutzer_id`, `h_system` (`H`/`B`), `vorzeichen` (`silben`/`zeichen`), `klang` (`synth`/`klavier`), `tagesziel_min`, `toleranz_cent`, `stimmlage`, `umfang_tief`, `umfang_hoch` |
| `lektion_status` | `nutzer_id`, `lektion_key`, `freigeschaltet_am`, `abgeschlossen_am` |
| `item_status` | `nutzer_id`, `item_key`, `box`, `faellig_am`, `richtig`, `falsch`, `zuletzt_am`, `letzter_aufstieg_am` |
| `sitzung` | `nutzer_id`, `art` (`drill`/`singen`/`test`), `trainer`, `start`, `ende`, `aktive_sekunden` |
| `frage` | `sitzung_id`, `nutzer_id`, `item_key`, `daten_json` (gespielte Töne), `antwort`, `korrekt`, `reaktion_ms`, `gestellt_am`, `beantwortet_am` |
| `sing_versuch` | `sitzung_id`, `nutzer_id`, `uebung`, `ziel_midi`, `abweichung_cent`, `stabilitaet_cent`, `einschwing_ms`, `treffer`, `oktavfehler`, `kurve_json` |
| `stimmtest` | `nutzer_id`, `tief_midi`, `hoch_midi`, `vorschlag`, `datum` |
| `abzeichen` | `nutzer_id`, `abzeichen_key`, `stufe`, `erhalten_am` |
| `merkhilfe` | `nutzer_id`, `item_key`, `text` |

Lektionen, Items, Learn-Texte und Abzeichen-Definitionen liegen **im Code** (`app/lernen/katalog.py`, `app/abzeichen.py`), nicht in der DB. In der DB stehen nur stabile Schlüssel.

---

## 8. Abzeichen und Medaillen (ohne Erinnerungen)

Erscheinen als Hinweis am Ende einer Sitzung und auf der Profilseite.

| Abzeichen | Bedingung |
|---|---|
| Erster Ton | erste abgeschlossene Sitzung |
| Dranbleiben (Bronze/Silber/Gold) | Tagesziel an 3 / 7 / 30 Tagen in Folge |
| Medaille je Trainer (Bronze/Silber/Gold) | erste Lektion abgeschlossen / Hälfte der Lektionen / alle Lektionen und alle Einheiten ≥ Box 4 |
| Punktlandung | 10 gesungene Zieltöne in Folge im Toleranzbereich |
| Fels in der Brandung | 5 s Ton halten mit Stabilität unter 10 Cent |
| Vermessen | Stimmtest gemacht |
| Fleißig (Bronze/Silber/Gold) | 100 / 1000 / 5000 beantwortete Fragen |

Grafiken: eigene schlichte SVG-Plaketten im Stil der App.

---

## 9. Seiten

| Pfad | Inhalt |
|---|---|
| `/login`, `/einladung/{token}` | Anmeldung, Konto per Einladung anlegen |
| `/` | Start: Tagesziel-Ring, Serie, „Weiter üben“, Kacheln der 5 Trainer und „Singen“ |
| `/trainer/{trainer}` | Lektionskarten mit Status, „Lernstand“ |
| `/trainer/{trainer}/lektion/{key}` | Learn-Karte, dann Drill |
| `/trainer/{trainer}/lernstand` | transparente Boxenübersicht, Verwechslungen |
| `/singen` | Live-Anzeige, Übungen, Stimmtest |
| `/statistik` | Übungen pro Woche, Trefferquote pro Trainer, Singen-Werte |
| `/einstellungen` | Notation, Klang, Tagesziel, Toleranz, Stimmlage, Passwort |
| `/admin` | Nutzer, Einladungen, Rollen (Admin-Ernennung nur Superadmin) |
| `/healthz` | Healthcheck für Docker |

Mobile first, Bedienung mit dem Daumen, große Antwort-Buttons. Desktop bekommt dieselbe Oberfläche, breiter gesetzt.
