# What is this?
Basically, my school switched to All4Schools, which aims to enhance the experience of students and teachers by providing
a solution for school management, substitution plans, class management, grades managament and so on.

The problem is, that the dashboard looks very bad and unpolished, especially on mobile devices. Me and others in my class
were so frustrated that I decided to vibe code a privacy respecting self-hosted substitution plan.

Please notice: This project is not suited as a one click install for yourself. This is basically just open-source for
transparency. I might migrate this project into a real project with guide and installers, so that you can run this too,
but for now this is not planned.

Most of the descriptions are intentionally in German. This may or may not be changed in the future. Please notice, tha
the logic + API endpoints that I am actually using are NOT documented in this project for safety reasons. If you want
to replicate this, I can tell you about them. Please use my contact methods on my profile readme for more info.

# AI Disclaimer
I myself am a Desktop App Developer with Python and QML. I know basically NOTHING about Web Development. I can do real
programming and I have 5+ years experience in it, but just with another stack. This is the reason why 100% of the code
in this repository is AI generated. However, it's managed, tested and guided by a human behind the scenes. If you don't
like that, make your own :)

# VPlan

Eigenständige mobile Vertretungsplan-App mit Svelte, TypeScript, Vite, Tailwind CSS und einem
Starlette-Backend.

## Einrichtung

```bash
cp .env.example .env
npm ci
uv sync --all-groups
```

In `.env` müssen mindestens die drei autorisierten API-Endpunkte, API-Token, School-ID und die
akzeptierten Antworten gesetzt werden. Die Datei ist ignoriert und darf nicht committet werden.

Antwortet die offizielle Plan-API mit `401` oder `403`, ruft das Backend einmalig den in
`VPLAN_API_REFRESH_URL` konfigurierten Refresh-Endpunkt mit dem bisherigen Bearer-Token auf. Ein
syntaktisch gültiges neues JWT ersetzt `VPLAN_API_TOKEN` atomar in `.env`; anschließend wird der
Planabruf genau einmal wiederholt. Scheitert der Refresh oder wird der neue Token weiterhin
abgewiesen, erstellt das Backend über `VPLAN_API_AUTH_URL` und die optionalen Werte `USERNAME`
und `PASSWORD` eine neue `curl-cffi`-Session. Cookies werden nur im Arbeitsspeicher gehalten; ein
in Antwort oder Autorisierungsheader enthaltenes JWT wird ebenfalls atomar in `.env` übernommen.
Fehler werden ohne Zugangsdaten oder Token-Inhalte im Serverterminal gemeldet. Damit der erneuerte
Token einen Neustart überlebt, sollte er ausschließlich aus dieser lokalen `.env` und nicht
zusätzlich aus einer extern gesetzten, veralteten Umgebungsvariable kommen.

Die offizielle Plan-API wird zwischen 06:00 und 22:00 Uhr im Abstand von mindestens fünf Minuten
abgerufen. Von 22:00 bis 06:00 Uhr finden keine Upstream-Abrufe statt; ein in dieser Zeit
gestarteter Server wartet vor dem ersten Abruf bis 06:00 Uhr. Alle Zeiten beziehen sich auf
`Europe/Berlin`.

Frontend entwickeln:

```bash
npm run dev
```

Produktions-Build und Serverstart:

```bash
npm run build
uv run uvicorn backend.app:app --host 127.0.0.1 --port 8001 --workers 1 --no-access-log
```

Genau ein Worker ist erforderlich, weil Fehlversuche, IP-Sperren und Sitzungen absichtlich nur
bis zum Neustart im Arbeitsspeicher existieren. Der öffentliche Einstieg für
`vplan.echteralsfake.me` läuft über einen Privex-Relay in Schweden und von dort verschlüsselt zur
physischen Ursprungshardware in Deutschland. Der lokale Proxy leitet auf
`http://localhost:8001`, erhält den originalen Host und setzt die ursprüngliche Besucheradresse im
historisch benannten `CF-Connecting-IP`-Header. Cloudflare ist nicht mehr an der
Inhaltsübertragung beteiligt. Natives Encrypted Client Hello ist am öffentlichen Einstieg aktiv;
Post-Quanten-Verschlüsselung ist noch nicht aktiv. Der übrige Server bleibt auf Port 8000.

## Lokaler LAN-Test

Für einen direkten HTTP-Test von einem anderen Gerät im lokalen Netz müssen in `.env` der lokale
Host erlaubt und die ausschließlich für HTTPS beziehungsweise den öffentlichen Relay-/Tunnelweg
vorgesehenen Optionen vorübergehend deaktiviert werden:

```env
VPLAN_PUBLIC_HOST=192.168.0.20
VPLAN_TRUST_CLOUDFLARE_IP=false
VPLAN_SECURE_COOKIE=false
VPLAN_UPGRADE_INSECURE_REQUESTS=false
```

Danach den Server mit `--host 0.0.0.0` neu starten. Für den öffentlichen Betrieb müssen
`VPLAN_PUBLIC_HOST` wieder die öffentliche Domain und die drei booleschen Optionen wieder `true`
sein. Insbesondere verhindert die deaktivierte HTTPS-Hochstufung nur im lokalen HTTP-Test, dass
der Browser Assets per TLS von einem reinen HTTP-Uvicorn-Port anfordert.

## Private Lehrkraftliste importierenWARNING:  Invalid HTTP request received.
WARNING:  Invalid HTTP request received.
WARNING:  Invalid HTTP request received.
WARNING:  Invalid HTTP request received.
WARNING:  Invalid HTTP request received.
WARNING:  Invalid HTTP request received.
WARNING:  Invalid HTTP request received.
WARNING:  Invalid HTTP request received.
WARNING:  Invalid HTTP request received.
WARNING:  Invalid HTTP request received.
WARNING:  Invalid HTTP request received.
WARNING:  Invalid HTTP request received.
WARNING:  Invalid HTTP request received.
WARNING:  Invalid HTTP request received.
WARNING:  Invalid HTTP request received.
WARNING:  Invalid HTTP request received.
WARNING:  Invalid HTTP request received.
WARNING:  Invalid HTTP request received.

Eine vorhandene UTF-8-Textdatei mit genau einem Namen pro Zeile kann als zusätzliche private
Redaktionsliste importiert werden. Unterstützt werden Einträge wie `Frau Beispiel`,
`Herr Beispiel` oder `Frau Dr. Beispiel`. Den VPlan-Server vorher beenden, damit Cache und
Datenbank nicht gleichzeitig durch zwei Prozesse verändert werden:

```bash
uv run python -m backend.manage import-teachers /absoluter/pfad/lehrkraefte.txt
```

Der Befehl prüft die gesamte Datei vor dem Schreiben, dedupliziert die Einträge, speichert
Titelvarianten ausschließlich für das aktuelle Schuljahr und bereinigt einen vorhandenen
Plan-Cache unmittelbar. Seine JSON-Ausgabe enthält nur Anzahlen und Statuswerte, niemals Namen.
Ungültige Eingaben werden vollständig abgewiesen; `lineNumbers` nennt ausschließlich die
betroffenen Zeilennummern. Die Quelldatei außerhalb des Repositories aufbewahren und nach dem
Import wieder entsprechend dem eigenen Löschkonzept behandeln. Nach dem Import kann der Server
normal gestartet werden. Zum Schuljahreswechsel wird die private Redaktionsliste automatisch
gelöscht und muss bei weiterem Bedarf erneut importiert werden.

## Datenschutz und Laufzeitdaten

Die rohe API-Antwort, Quell-IDs und Lehrerobjekte werden nicht im öffentlichen Cache gespeichert.
Lehrkraftnamen werden nur intern zur Redaktion verarbeitet; die private Redaktionsliste und
gelernte Kurse werden jährlich gelöscht. Eine manuell importierte Quelldatei wird nur lokal
gelesen und nicht vom Dienst kopiert. Klasse, persönliche Kurse, Fachnamen, Darstellung und
Disclaimer-Bestätigung bleiben im Browser. Freiwillige Fehlermeldungen liegen maximal 180 Tage
in `data/vplan.db`.

Die optionalen Zugangsdaten des Betreibers verbleiben in `.env`, werden nur bei erforderlicher
Neuanmeldung per HTTPS an den offiziellen Schulserver übertragen und niemals an Browser,
Datenbank, Cache oder Logs weitergegeben. Sitzungscookies des Schulservers verbleiben im RAM.

`data/`, `.env`, `dist/`, `.venv/` und `node_modules/` sind nicht Teil des Repositories. Rohe
Beispielantworten ebenfalls nicht committen.

## Prüfungen

```bash
npm run check
npm run lint
npm test
npm run build
UV_CACHE_DIR=/tmp/vplan-uv-cache uv run pytest
uv run python -m py_compile backend/*.py tests/*.py
```

Die vollständigen Architektur- und Datenschutzverträge stehen in `VPLAN_CONTEXT.md`.
