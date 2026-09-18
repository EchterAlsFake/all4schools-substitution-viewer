# VPlan production operation

Production lives in `/srv/vplan`, runs as `eaf-vplan`, and listens only on
`127.0.0.1:8001`. The working repository stays in Dokumente. The shared procedure
is documented in `../Server/deploy/OPERATIONS.md` from this repository root.

Use `sudo eaf-deploy vplan` to test, build and update VPlan. Python dependencies are
resolved from `pyproject.toml` without uv lockfiles; Node uses `npm ci`. The runtime
environment excludes test dependencies. One Uvicorn worker owns all sessions,
bans and background synchronization. Restarting clears sessions and bans.

The private `.env` is editable by the operator but read-only to the service.
The service writes refreshed JWTs atomically to `data/api-token` with mode 0600.
A valid saved token wins over the bootstrap value. To reset it, stop `eaf-vplan`,
remove that exact saved-token file, update `.env`, and start the service.
Never copy the token file into `dist/`, `public/`, a log, or version control.

Uvicorn uses `--no-proxy-headers`: the application must see Caddy as the loopback
socket peer. Caddy supplies the relay-preserved visitor IP in `CF-Connecting-IP`,
overwriting visitor input. Secure cookies and HTTPS browser policies remain enabled.

Pre-update backups contain the private SQLite database and token. They are root-only
under `/srv/.eaf-backups` and require manual deletion within seven days and before
data-retention/school-year deadlines. Backups are not served by the website.
