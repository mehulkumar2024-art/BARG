# Ubuntu deployment handoff

Target: Ubuntu 24.04, Python backend bound to 127.0.0.1:8080, Caddy >=2.8 on HTTPS, authenticated read-only access. Use a dedicated subdomain such as monitor.cartifly.me after the owner points its DNS to the host. Keep the existing GitHub Pages site separate. This monitors the Ubuntu host, not visitors' laptops.

These are reviewable templates, not a completed deployment. A server account, DNS access and a privately chosen password are still required. Do not paste passwords into chat or commit hashes/configured credentials.

1. Provision an Ubuntu VM. Install Python/venv, Node >=20 and Caddy following their official installation documentation. Create an unprivileged `barg` service account.
2. Place the repository in /opt/barg, create /opt/barg/.venv and install requirements.txt. Run `npm ci` and `npm run build` inside frontend WITHOUT the Pages /BARG/ base option. The private dashboard is served at the subdomain root.
3. Install barg.service into /etc/systemd/system; verify paths and account before enabling it. The monitor is unprivileged, so protected processes may be skipped. Keep kernel experiments separate from this service.
4. Run `caddy hash-password` interactively. Replace the hostname in BOTH places in Caddyfile.example and replace its hash placeholder. Install the configured file as /etc/caddy/Caddyfile. Never use plain HTTP with Basic Authentication.
5. Run `caddy validate --config /etc/caddy/Caddyfile` and `systemd-analyze verify /etc/systemd/system/barg.service`. Enable/restart the services only after validation. Permit HTTPS/HTTP for Caddy; keep port 8080 private.
6. Confirm an unauthenticated /api/status request returns 401; valid authentication permits the dashboard and WebSocket; an authenticated WebSocket with a foreign Origin returns 403; POST/PUT requests return 403; TLS is valid; no remote connection to port 8080 succeeds.
7. Confirm real host readings and freshness after login. The same-origin gateway covers dashboard assets, API, exports and WebSocket. Credentials are removed before forwarding. Caddy rejects foreign origins before rewriting headers for the loopback-only backend. Do not remove that check.

Caddy references: https://caddyserver.com/docs/caddyfile/directives/basic_auth and https://caddyserver.com/docs/caddyfile/directives/reverse_proxy . The password hash is generated privately; no default credential is supplied.

Rollback: stop the BARG service and remove only this site's Caddy block after checking other hosted sites. Do not remove shared Caddy configuration. Back up /var/lib/barg before upgrading or moving telemetry.
