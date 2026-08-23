# Vertretungsplan – Kontext für zukünftige Coding-Agents

> Stand: 23. August 2026. Dieses Dokument beschreibt nur den eigenständigen Vertretungsplan.
> Vor VPlan-Änderungen immer diese Datei vollständig lesen und `git status` prüfen.

## 1. Produkt und Abgrenzung

VPlan ist ein privates, inoffizielles Schülerprojekt. Es stellt den offiziellen Plan
mobile-first und barrierearm dar, ersetzt ihn aber nicht. Der Dienst liegt in einem eigenständigen
Repository und läuft unabhängig vom kommerziellen Flask-Server:

- kommerzieller Server: Port 8000;
- VPlan: FastAPI/Uvicorn auf Port 8001;
- öffentliche VPlan-Route: `https://vplan.echteralsfake.me/`;
- der alte Pfad `/vplan` leitet innerhalb des neuen Dienstes dauerhaft auf `/` um;
- `main.py` enthält keine VPlan-Routen, Synchronisation, Modelle oder Assets mehr.

Die beiden SQLite-Datenbanken sind getrennt. Alte VPlan-Tabellen in der kommerziellen
`server.db` werden absichtlich weder migriert noch gelöscht.

## 2. Architektur und relevante Dateien

Frontend:

| Pfad | Aufgabe |
| --- | --- |
| `src/App.svelte` | Routing, Initialisierung und Zugangszustand |
| `src/components/Gate.svelte` | Sicherheitsfrage und Sperranzeige |
| `src/components/PlanApp.svelte` | Plan, Filter, Personalisierung, Dialoge und Feedback |
| `src/components/SiteHeader.svelte` | Kopfbereich, Sprache, Theme und responsive Tagesnavigation |
| `src/components/LegalPage.svelte` | Datenschutz und Verantwortlicher |
| `src/components/TranslatorPage.svelte` | rein lokaler Übersetzungseditor |
| `src/lib/api.ts` | typisierter Zugriff auf die eigene FastAPI |
| `src/lib/day-navigation.ts` | flüchtige Verbindung zwischen Plan und Tagesnavigation im Header |
| `src/lib/refresh-schedule.ts` | Berliner Zeitfenster für die automatische Cache-Aktualisierung |
| `src/lib/storage.ts` | fehlertoleranter Zugriff auf `localStorage` |
| `public/i18n/*.json` | deutscher Quellkatalog, Englisch und Sprachmetadaten |
| `public/sw.js` | PWA-App-Shell ohne Plan-/API-Cache |

Backend:

| Pfad | Aufgabe |
| --- | --- |
| `backend/app.py` | FastAPI, Routen, Header, Hintergrundjobs und statische Auslieferung |
| `backend/auth.py` | RAM-basierte Zugangsschranke und IP-Pseudonymisierung |
| `backend/upstream.py` | offizieller API-Abruf, Validierung, Redaktion und atomarer Cache |
| `backend/database.py` | separate SQLite-Datenbank über SQLAlchemy |
| `backend/schemas.py` | strikte Pydantic-Eingangsmodelle |
| `backend/config.py` | lokale `.env`, Validierung und sichere nicht-sensible Defaults |
| `backend/manage.py` | lokale Operator-Befehle für validierte private Datenimporte |
| `tests/` | Backend-, Datenschutz-, Redaktions- und i18n-Verträge |

Build und Laufzeit:

- Vite, TypeScript, Svelte 5 und Tailwind CSS 4;
- FastAPI, Uvicorn, SQLAlchemy und `curl-cffi`;
- `package-lock.json` und `uv.lock` sind reproduzierbare Lockfiles;
- `node_modules/`, `dist/`, `.venv/`, `.env` und `data/` bleiben unversioniert.

## 3. Datenfluss

```text
offizielle Substitution-API
  │  Bearer-Token; POST; HTTP/3; Chrome-Impersonation
  ├─ bei 401/403: Refresh-API → neues JWT atomar in .env → erneuter Abruf
  └─ falls weiter unautorisiert: JwtAuth → neue RAM-Session → letzter Abruf
  ▼
Pydantic-Limits und Schema-Prüfung
  │
  ├─ Lehrkraftobjekte/IDs nur flüchtig zur Redaktion verwenden
  ├─ bekannte Lehrkraftnamen intern pro Schuljahr lernen oder lokal importieren
  └─ Kurskennungen intern pro Schuljahr lernen
  ▼
öffentliche Felder normalisieren → Kommentare redigieren → SHA-256
  ▼
atomarer, bereits bereinigter JSON-Cache (nur bei Inhaltsänderung)
  ▼
GET /api/plan hinter Zugangsschranke
  ▼
Svelte-Oberfläche; persönliche Auswahl bleibt im Browser
```

Planabruf, Token-Refresh und optionale Neuanmeldung verwenden ausschließlich die verpflichtenden
HTTPS-Endpunkte aus `VPLAN_API_URL`, `VPLAN_API_REFRESH_URL` und `VPLAN_API_AUTH_URL`. Es gibt
dafür absichtlich keine fest eingebauten Defaults. Die echten Endpunkte stehen nur in der lokalen
`.env` und werden weder in Quellcode noch in getrackten Beispielen oder Dokumentation genannt.

Nur `401` und `403` lösen einen Refresh aus. Der aktuelle Bearer-Token wird dabei mit
`curl-cffi`, Chrome-Impersonation und demselben HTTP/3-/HTTP/2-Fallback an den Refresh-Endpunkt
gesendet. Das Ergebnis muss ein syntaktisch gültiges JWT sein. Es ersetzt
`VPLAN_API_TOKEN` atomar in der lokalen `.env`; danach folgt ein erneuter Planabruf. Scheitert der
Refresh oder wird auch der erneuerte Token mit `401`/`403` abgewiesen, wird genau eine neue
`curl-cffi`-Session erstellt und `JwtAuth` mit `Username`, `Password` und `Pin: null` aufgerufen.
Cookies verbleiben in dieser RAM-Session. Ein syntaktisch gültiges JWT aus Antwort oder
Autorisierungsheader ersetzt ebenfalls atomar `VPLAN_API_TOKEN`; bei einer reinen Cookie-Sitzung
wird der abgelaufene Bearer beim letzten Planabruf weggelassen. Fehler beim Refresh, Login,
Speichern oder letzten Abruf werden ohne Geheimnisse im Terminal protokolliert und der letzte
gültige Cache bleibt erhalten.

Der Request fragt den aktuellen Tag bis zum nächsten Schultag ab. Am Freitag reicht das Fenster
bis Montag. `curl-cffi` versucht zuerst HTTP/3 mit `impersonate="chrome"`. Nur bei einem
Transportfehler folgt ein HTTP/2-Fallback; HTTP-Fehler werden nicht durch erneute Protokollwahl
verschleiert. Zwischen 06:00 und 22:00 Uhr wird standardmäßig alle 300 Sekunden synchronisiert.
Von 22:00 Uhr einschließlich bis 06:00 Uhr finden keine Upstream-Abrufe statt; auch ein in der
Sperrzeit gestarteter Prozess wartet vor seinem ersten Abruf. Maßgeblich ist `Europe/Berlin`.

Die rohe Antwort, originale IDs und Lehrerobjekte werden nie in den Plan-Cache geschrieben.
Kommentare werden von expliziten `LiGyDe.*`-Werten, Namen mit Anrede, „Aufgaben von …“ und den
in derselben beziehungsweise früheren Antworten erkannten Namen bereinigt. Eindeutige
Freitextkontexte wie `LiGyDe.*`, „Aufgaben von …“ und zwei Kürzel vor einem Raum werden dabei
auch für spätere Abrufe gelernt. Die interne
Redaktionsliste wird nur in der separaten lokalen Datenbank gehalten, nie ausgeliefert und zum
Schuljahreswechsel am 1. August gelöscht. Dies ist eine private Verarbeitung zum Entfernen der
Namen, keine öffentliche Speicherung.

Ein kanonischer SHA-256 über die öffentlichen Tage verhindert unnötige Cache-Neuschreibungen.
Fehlerhafte, übergroße oder ungültige Antworten überschreiben keinen letzten gültigen Cache.
Fehlt der Cache beim Erststart, liefert `/api/plan` kontrolliert `503 plan_unavailable`, bis ein
gültiger Abruf gelang. Nach einem Abruffehler wird ein vorhandener Plan mit `stale: true`
gekennzeichnet.

## 4. Öffentliches Planformat

Das Frontend erhält ausschließlich die bereinigte Form:

```json
{
  "version": "sha256",
  "lastSuccessfulFetchAt": "2026-08-22T10:00:00+00:00",
  "lastAttemptAt": "2026-08-22T10:02:00+00:00",
  "sourceFrom": "2026-08-22T00:00:00",
  "sourceTo": "2026-08-24T23:59:59",
  "schoolYear": "2026-2027",
  "learnedCourseCodes": ["12_CHE1"],
  "stale": false,
  "days": [
    {
      "date": "2026-08-24",
      "entries": [
        {
          "id": "nicht-originaler-hash",
          "kind": "change",
          "start": "2026-08-24T07:45:00+02:00",
          "end": "2026-08-24T08:30:00+02:00",
          "oldSubject": "CHE",
          "newSubject": "",
          "oldRooms": ["A415"],
          "newRooms": [],
          "classes": ["12_CHE1"],
          "comment": "Aufgaben von Lehrkraft"
        }
      ]
    }
  ]
}
```

Typ `1` wird `change`, Typ `2` `cancelled`, Typ `3` `self_study`; unbekannte Werte werden
`unknown`. Niemals neue Quellfelder pauschal durchreichen. Jede Erweiterung braucht eine
explizite Positivliste, Längenbegrenzung und einen Test, dass Lehrerobjekte und IDs fehlen.

## 5. Zugangsschranke

Vor dem Plan muss eine in den Sprachkatalogen gepflegte Ortsfrage beantwortet werden. Die
akzeptierten Antworten stehen ausschließlich kommasepariert in `VPLAN_GATE_ANSWERS` der lokalen
`.env`; echte Antworten nie in getrackte Beispiele, Tests oder Dokumentation schreiben.

Verhalten:

- Antwort wird getrimmt, großgeschrieben und von Whitespace befreit;
- nach drei Fehlern ist die öffentliche Client-IP bis zum Prozessneustart gesperrt;
- Sperren, Versuche und Sitzungen existieren ausschließlich im RAM;
- die rohe IP wird sofort mit einem zufälligen, pro Start neuen HMAC-Schlüssel pseudonymisiert;
- `CF-Connecting-IP` wird nur vertraut, wenn die direkte Socket-Gegenstelle Loopback ist;
- fehlt hinter dem erwarteten Tunnel die vertrauenswürdige IP, schlägt der Dienst geschlossen fehl;
- die erfolgreiche Sitzung verwendet ein zufälliges `HttpOnly`, `Secure`, `SameSite=Strict`-Cookie;
- ein gesperrter Client bleibt auch mit altem Cookie gesperrt;
- schreibende Endpunkte prüfen `Origin`/`Sec-Fetch-Site` zusätzlich.

Wichtig: VPlan in Produktion mit genau einem Uvicorn-Worker betreiben. Mehrere Prozesse hätten
getrennte RAM-Sperren und Sitzungen und würden die zugesagte „bis zum Serverneustart“-Semantik
brechen. Mehrere Threads desselben Prozesses sind durch Locks abgesichert. Personen hinter
derselben öffentlichen IP können gemeinsam von einer Sperre betroffen sein; der Rechtstext
weist darauf hin.

## 6. HTTP-Routen und Sicherheitsheader

- `GET /healthz`: konfiguriert/nicht konfiguriert, ohne Geheimnisse;
- `GET /api/auth/status`: Freigabe, Sperre, Restversuche;
- `POST /api/auth/answer`: Antwortprüfung und Sitzung;
- `POST /api/auth/logout`: Sitzung widerrufen;
- `GET /api/plan`: bereinigter Plan, nur mit Freigabe;
- `POST /api/feedback`: freiwillige anonyme Fehlermeldung, nur mit Freigabe;
- `GET /privacy`, `/imprint`, `/translate`, `/credits`, `/changelog`: Svelte-Routen;
- `GET /vplan`: `308` nach `/`;
- `GET /sw.js`, `/manifest.webmanifest`, `/i18n/*`, `/icons/*`, `/assets/*`: App-Ressourcen.

API und App-Einstieg verwenden `Cache-Control: no-store`. CSP erlaubt nur eigene Ressourcen,
Frames sind verboten, Referrer werden nicht gesendet und unnötige Browserberechtigungen sind
deaktiviert. `upgrade-insecure-requests` ist in Produktion aktiv, kann aber über
`VPLAN_UPGRADE_INSECURE_REQUESTS=false` ausschließlich für direkte lokale HTTP-Tests deaktiviert
werden, damit Browser die Assets nicht gegen den reinen HTTP-Uvicorn-Port auf HTTPS hochstufen.
Der Uvicorn-Zugriffslog bleibt im Produktionskommando ausgeschaltet. Query-Strings, Token,
Antworten oder Besucheradressen dürfen auch nicht durch einen vorgeschalteten Prozess protokolliert
werden.

## 7. Oberfläche und Browserdaten

Die Svelte-App behält die bisherigen Funktionen:

- responsive Tag-Tabs im freien Headerbereich und automatische Auswahl: vor 15 Uhr heute,
  danach nächster verfügbarer Tag; auf schmalen Displays sind die Tabs horizontal scrollbar;
- die Browseransicht liest den eigenen Plan-Cache tagsüber alle fünf Minuten neu und setzt diese
  automatischen Aufrufe zwischen 22:00 und 06:00 Uhr (Europe/Berlin) aus; der einmalige Abruf beim
  Öffnen zeigt nachts lediglich den vorhandenen Cache und löst keinen Upstream-Abruf aus;
- Suche und Filter nur für Ausfälle;
- optionaler persönlicher Plan für Klassen 5–10 und frei wählbare Kurse 11–12;
- während des Schuljahres automatisch gelernte Kursauswahl plus manuelle Kurscodes;
- lokale Fachnamen, optionale lokale Lehrernamen und acht feste Akzentfarben;
- Dark/Light Mode, Deutsch/Englisch, PWA-Installation, Credits und Changelog;
- verpflichtender Disclaimer mit Checkbox beim ersten Planaufruf;
- Verantwortlicher, Datenschutz und ein rein lokaler Übersetzungseditor;
- externer GitHub-Link zum öffentlichen Quellcode ohne eingebettete GitHub-Inhalte;
- freiwillige Fehlermeldung mit Datenschutzbestätigung.

Planwerte werden durch Svelte als Text ausgegeben, niemals als HTML. Dynamische Werte dürfen
nicht über `innerHTML`, `outerHTML` oder ähnliche APIs eingefügt werden.

Lokale Schlüssel:

| Schlüssel | Inhalt |
| --- | --- |
| `vplan-theme` | `dark` oder `light` |
| `vplan-language` | freigeschalteter Sprachcode |
| `vplan-preferences` | Aktivierung, Jahrgang, Klasse und Kursauswahl |
| `vplan-subject-overrides` | lokale Namen, Lehrernamen und Farbe je Fachschlüssel |
| `vplan-disclaimer-accepted-v1` | Bestätigung des Nutzungshinweises |

Diese Daten werden nicht an den Server gesendet. Speicherfehler dürfen die Grundfunktion nicht
unbenutzbar machen. Der Service Worker speichert nur die statische App-Shell, nie `/api/*` oder
einen Plan. Alte Worker mit Scope `/vplan` werden beim Start entfernt.

## 8. Datenbank und Datenschutz

`data/vplan.db` enthält ausschließlich:

- `learned_courses`: Kurscode und Schuljahr;
- `learned_teacher_names`: private Redaktionsnamen und Schuljahr;
- `feedback`: Meldung und UTC-Zeitpunkt;
- `feedback_rate_windows`: anonymer Gesamtzähler pro Minute.

Die konkrete Klasse/Kursauswahl eines Kindes und die IP werden nie in SQLite gespeichert.
Feedback ist 10–1500 Zeichen lang; erkennbare E-Mail-Adressen, Links, Telefonnummern und HTML
werden abgewiesen. Meldungen werden nach 180 Tagen, Zähler innerhalb eines Tages gelöscht. Das
Limit ist absichtlich global und anonym. Alle Zugriffe erfolgen über SQLAlchemy mit gebundenen
Werten und Transaktions-Rollback.

Eine optionale UTF-8-Lehrkraftliste im Format `Frau/Herr Name` wird ausschließlich über den
lokalen Operator-Befehl `uv run python -m backend.manage import-teachers DATEI` eingelesen. Der
Befehl validiert die gesamte Datei vor dem Schreiben, speichert Namen und Varianten nur im
aktuellen Schuljahr und bereinigt einen vorhandenen Cache atomar. Er kopiert die Quelldatei nicht
und gibt weder Namen noch Inhalte aus. Während des Imports muss der VPlan-Prozess beendet sein;
die private Quelldatei bleibt außerhalb des Repositories und unter Verantwortung des Betreibers.

`USERNAME` und `PASSWORD` sind ausschließlich lokale Zugangsdaten des Betreibers. Sie bleiben in
`.env`, werden nur bei einem erforderlichen Sitzungsaufbau per HTTPS an den offiziellen
`JwtAuth`-Endpunkt übertragen und gelangen nie an Besucher, SQLite, Plan-Cache oder Logs.
Offizielle Sitzungscookies existieren ausschließlich im RAM und enden spätestens mit dem
VPlan-Prozess.

Jede Änderung an IP-Verarbeitung, Cookies, Browser-Speicherung, API-Weitergabe, Datenbank oder
Löschfristen muss gleichzeitig in `LegalPage.svelte`, `PlanApp.svelte` und allen freigeschalteten
Sprachkatalogen wahrheitsgemäß dokumentiert werden.

## 9. Übersetzungen

`public/i18n/de.json` ist Quelle und Fallback. Freigeschaltete Kataloge müssen dieselben
Schlüssel und Platzhalter besitzen. Noch nicht menschlich geprüfte Übersetzungen bleiben
`reviewed: false`/Beta. Neue sichtbare Texte, Titel, Platzhalter, Tooltips und Accessibility-Texte
werden nie ausschließlich hart codiert, sondern über `t()` eingebunden.

Katalogwerte enthalten kein HTML. Offizielle Planinhalte, persönliche Fachnamen und lokal
eingetragene Lehrernamen werden nicht übersetzt. Der Übersetzungseditor importiert und exportiert
nur im Browser und besitzt keinen Upload-Endpunkt.

## 10. Konfiguration und Betrieb

Alle VPlan-Werte gehören in die lokale `.env`:

- `VPLAN_API_TOKEN` – erforderliches Geheimnis;
- `VPLAN_API_URL` – erforderlicher HTTPS-Endpunkt für den Planabruf;
- `VPLAN_API_REFRESH_URL` – HTTPS-Endpunkt für die automatische JWT-Erneuerung;
- `VPLAN_API_AUTH_URL` – HTTPS-Endpunkt für den optionalen neuen Sitzungsaufbau;
- `USERNAME`, `PASSWORD` – optionale lokale Betreiber-Zugangsdaten für `JwtAuth`;
- `VPLAN_SCHOOL_ID` – erforderliche positive ID;
- `VPLAN_GATE_ANSWERS` – erforderliche, kommaseparierte Antworten;
- `VPLAN_PUBLIC_HOST` – erwarteter öffentlicher Host;
- `VPLAN_TRUST_CLOUDFLARE_IP` – in Tunnel-Produktion `true`;
- `VPLAN_SECURE_COOKIE` – in HTTPS-Produktion `true`;
- `VPLAN_UPGRADE_INSECURE_REQUESTS` – CSP-HTTPS-Hochstufung, in Produktion `true`;
- `VPLAN_SYNC_ENABLED` – Hintergrundabruf, standardmäßig `true`;
- `VPLAN_SYNC_INTERVAL_SECONDS` – standardmäßig `300`, Minimum `300`;
- `VPLAN_REQUEST_TIMEOUT_SECONDS` – standardmäßig `20`;
- `VPLAN_MAX_RESPONSE_BYTES` – standardmäßig 5 MiB;
- `VPLAN_DATA_DIR`, `VPLAN_DATABASE_PATH`, `VPLAN_CACHE_PATH` – optionale lokale Pfade.

Relative Laufzeitpfade werden gegen das Repository-Root aufgelöst. Alle drei API-Endpunkte müssen
HTTPS verwenden, damit Token und Betreiber-Zugangsdaten nicht durch eine Fehlkonfiguration im
Klartext übertragen werden können.

Bei fehlendem Token, fehlenden oder ungültigen API-Endpunkten, ungültiger School-ID oder fehlenden
Antworten startet der Prozess zur Diagnose, aber Auth/Plan schlagen mit
`503 service_not_configured` geschlossen fehl. Geheimnisse und rohe Beispielantworten gehören nie
in Git; `example.json` ist im Root explizit ignoriert.

Build und Start:

```bash
npm ci
npm run build
uv sync --all-groups
uv run uvicorn backend.app:app --host 127.0.0.1 --port 8001 --workers 1 --no-access-log
```

Cloudflare/Tunnel muss `vplan.echteralsfake.me` auf `http://localhost:8001` leiten und den
originalen Host sowie `CF-Connecting-IP` bis zum lokalen Loopback-Ursprung erhalten. Der
kommerzielle Dienst bleibt auf Port 8000. `curl-cffi`-HTTP/3 auf Android/Termux ist
plattformabhängig; der kontrollierte HTTP/2-Fallback gehört deshalb zum Betriebsdesign.

## 11. Pflichtprüfungen

Vor jeder Übergabe mindestens:

```bash
npm run check
npm run lint
npm test
npm run build
UV_CACHE_DIR=/tmp/vplan-uv-cache uv run pytest
uv run python -m py_compile backend/*.py tests/*.py
git diff --check
```

Zusätzlich den Diff prüfen auf:

- Lehrerobjekte, IDs, Tokens, akzeptierte Antworten und rohe Plandaten;
- nicht übersetzte sichtbare Texte oder abweichende Platzhalter;
- Aussagen im Datenschutz, die der Implementierung widersprechen;
- unsichere DOM-APIs, Inline-Handler oder dynamische Codeausführung;
- neue Kopplung zum kommerziellen Dienst, Port 8000 oder dessen Datenbank.

Ein Live-Smoke-Test gegen die offizielle API erfolgt nur lokal mit dem echten Token. Niemals den
Token, vollständige Response-Inhalte oder Lehrkraftnamen in Testausgabe beziehungsweise Logs
schreiben.

## 12. Änderungsregeln

1. Nutzeränderungen und fachfremde Dateien im Worktree bewahren.
2. Quellantwort und Browserdaten als nicht vertrauenswürdig behandeln.
3. Neue Quellfelder nur explizit validieren und positiv auswählen.
4. Lehrkraftdaten vor dem öffentlichen Cache und vor jeder Ausgabe entfernen.
5. Personalisierung lokal halten; keine Schülerprofile serverseitig anlegen.
6. Neue Speicherung nur zusammen mit Minimierung, Löschregel, Rechtstext und Tests einführen.
7. Die Zugangsschranke nicht in mehrere Worker oder persistente IP-Listen aufteilen.
8. Mobile Bedienung, Tastatur, Dialoge, Dark Mode, leeren Erststart und veralteten Cache prüfen.
9. Sichtbare Texte immer synchron in alle Kataloge aufnehmen und Platzhalter testen.
10. Dieses Dokument bei Architektur-, Datenfluss-, Routen- oder Datenschutzänderungen anpassen.
