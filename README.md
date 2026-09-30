# DevOps monitoring system

A compact DevOps monitoring and troubleshooting application: collect telemetry, detect deterministic failure conditions, preserve incident evidence, and request an explanation. Built for a clear portfolio demonstration rather than production-scale observability.

**Stack:** React + TypeScript + Recharts, FastAPI, PostgreSQL, Prometheus, Docker Compose, and optional OpenAI Responses API.

## Run locally

Requirements: Docker Desktop or Docker Engine with Compose 2.24.4+, Python 3.12+ for the configuration helper, and available port 8080. Python is only needed to generate credentials; application dependencies run inside containers.

```sh
python3 scripts/configure.py --demo
docker compose up -d --build
```

Open [http://localhost:8080](http://localhost:8080). Local demo login: **admin / ThemistoDemo2026!**. The generated `.env` has random internal credentials and is excluded from Git. The helper refuses to overwrite existing configuration. For a chosen password, omit `--demo`.

Allow approximately 30–60 seconds for useful rolling metrics. No LLM key is required: incident analysis returns explicitly labeled, deterministic **Demo explanations** until a real key is configured. The application does not seed fake incidents or chart values.

```sh
docker compose ps
docker compose logs --tail=100 backend demo-service
docker compose down       # preserves PostgreSQL, metrics, and certificate volumes
```

## Reviewer walkthrough

1. Open Overview; see the service status, request count, rolling error rate, p95 latency, and open incidents.
2. Sign in with the local admin account.
3. Select **HTTP errors**, leave the duration at 60 seconds, and click **Simulate failure**.
4. An incident should appear within 90 seconds. Error logs may create a separate incident because each rule is independent.
5. Open **Elevated HTTP errors**. Inspect its immutable triggering metrics and related logs.
6. Click **Analyze incident**. Read the likely cause, explanation, troubleshooting steps, and uncertainty note. Without a key this is labeled **Demo explanation**.
7. The simulation stops automatically; after the rolling window clears and three healthy evaluations occur, the incident becomes resolved. Expect up to roughly 90 seconds after simulation expiry.
8. Sign out. Public visitors can still read saved results, but cannot create simulations or analyses.

The Metrics page offers 15-minute, one-hour, six-hour, and one-day charts. Logs supports service, level, and timestamp filters. Incident history supports service, type, and status filters. All times are stored in UTC and displayed in browser local time.

## Architecture and data flow

```text
Demo service ── /metrics ──> Prometheus ── fixed queries ──> FastAPI
     │                                                      │
     └── authenticated log batches ──> PostgreSQL <── detector loop
                                             │              │
Browser ── Caddy ── React + /api proxy ── FastAPI ── optional OpenAI API
```

The demo generates about two real HTTP requests per second against its own `/work` endpoint. Health checks and scrapes do not inflate application counters. Prometheus scrapes every five seconds. FastAPI runs one cancellable five-second detector loop in one worker. React polls every five seconds.

There are exactly five main Compose services: `frontend` (Caddy plus static React), `backend`, `postgres`, `prometheus`, and `demo-service`. Only the frontend publishes a host port. No Docker socket is mounted.

### Layout

```text
backend/app/
  main.py, config.py, database.py, models.py, schemas.py, security.py
  api/       # auth, metrics, logs, incidents, AI, demo-control endpoints
  services/  # Prometheus, logs, detector, AI integration
  rules/     # pure deterministic rules
backend/migrations/  # Alembic schema history
backend/tests/       # unit and PostgreSQL integration tests
demo-service/        # instrumented demo, load generator, bounded simulations
frontend/src/        # dashboard, typed API client, polling, charts
monitoring/          # Prometheus scrape configuration
frontend/tests/      # browser acceptance tests
scripts/             # credential helper and isolated test runner
```

### Detection semantics

| Condition | Default trigger | Severity |
| --- | --- | --- |
| HTTP errors | >10% 5xx over 60s; at least 20 requests | Warning |
| Latency | p95 >1s over 60s; at least 20 requests | Warning |
| Unavailable metrics | `up` absent or not 1 for 20s, after a 30s startup grace | Critical |
| Error logs | At least 5 ERROR logs within 60s | Warning |
| Process CPU | >80% of one CPU core for 30s | Warning |
| Resident memory | >256 MiB for 30s | Warning |

Thresholds are backend settings (`ERROR_THRESHOLD`, `LATENCY_THRESHOLD`, `MIN_REQUESTS`, `UNAVAILABLE_SECONDS`, `STARTUP_GRACE`, `ERROR_LOG_THRESHOLD`, `CPU_THRESHOLD`, `MEMORY_THRESHOLD`, `RESOURCE_SECONDS`, `DETECTION_INTERVAL`). Add them to the backend Compose environment when overriding defaults. Percentages use 0–100 units; memory uses MiB; latency uses seconds.

A PostgreSQL partial unique index permits only one open incident per service/rule. Repeated breaches update `last_seen_at`; three consecutive healthy evaluations resolve it. A later breach creates a new incident. Evidence is a snapshot of triggering metrics and up to 30 recent logs, preserved even after raw logs expire.

A reachable service with open incidents is **degraded**; a reachable service with no open incidents is **healthy**. Missing data and insufficient request samples are **unknown**, not zero or healthy. A Prometheus outage suspends metric-rule transitions and clears in-memory consecutive-evaluation timers, while log rules continue. A failed scrape triggers only the unavailable rule; stale application metrics cannot trigger or resolve other metric rules. Restarting the backend preserves incidents but conservatively restarts hold/recovery timers.

Request totals reset with the demo process. Error/latency windows use Prometheus counter rates and histograms; p95 is an approximation based on buckets. CPU is relative to one core and can exceed 100%; resources are **process metrics, not host-wide metrics**.

### Log delivery and retention

The demo batches up to 100 events, keeps at most 1,000 queued events plus one retry batch, retries with backoff up to 15 seconds, and deduplicates deliveries using UUID event IDs. A full queue discards its oldest entry and increments `demo_logs_dropped_total`. This educational queue is not durable across demo restarts. Old retry batches expire after seven days.

Logs are limited to 4,000 characters; bodies to 512 KB. Ingestion accepts known services and timestamps within retention, with at most one minute of future skew. Common credential patterns are redacted at ingestion and again before AI analysis. Only synthetic demo data should be sent to this public portfolio dashboard; redaction is not a general-purpose data-loss prevention system.

Raw logs are cleaned hourly after seven days; Prometheus retains seven days. Incidents and their evidence remain in PostgreSQL until an explicit database reset. Database growth from incident history is a documented small-demo tradeoff.

## API

| Method | Endpoint | Access |
| --- | --- | --- |
| GET | `/api/health` | Public; database readiness |
| GET | `/api/metrics/summary` | Public; optional `service_name` |
| GET | `/api/metrics/history` | Public; `service_name`, allowlisted `metric`, `minutes` 1–1440 |
| GET | `/api/logs` | Public; `service_name`, `level`, `since`, `until`, `limit`, `offset` |
| POST | `/api/logs` | Internal ingestion bearer credential |
| GET | `/api/incidents` | Public; `service_name`, `status`, `incident_type`, `limit`, `offset` |
| GET | `/api/incidents/{id}` | Public |
| POST | `/api/incidents/{id}/analyze` | Admin session + CSRF + matching Origin |
| POST | `/api/demo/simulate-failure` | Admin session + CSRF + matching Origin |
| GET | `/api/demo/status` | Public; optional `service_name` |
| POST | `/api/auth/login` | Matching Origin; throttled |
| POST | `/api/auth/logout` | Admin session + CSRF + matching Origin |
| GET | `/api/auth/me` | Public; session state and CSRF token for authenticated users |

Lists return `{items, total}`, default to 50 rows, and cap pages at 100. Time filters require an explicit timezone. Unknown services and metric names are rejected. No endpoint accepts arbitrary PromQL.

Simulation body: `{"service_name":"demo-service","mode":"http_errors","duration_seconds":60}`. Modes: `http_errors`, `latency`, `error_logs`, `unavailable`. Duration: 15–120 seconds. Only one active simulation per service; conflicts return 409. Simulations expire using a monotonic clock inside the demo; unavailable mode fails `/metrics` while leaving control/health reachable. Resource thresholds are implemented but CPU/memory exhaustion simulations are intentionally omitted.

## Real AI configuration

Set `OPENAI_API_KEY` in `.env`, optionally change `OPENAI_MODEL` (default `gpt-4o-mini`), then recreate the backend:

```sh
docker compose up -d backend
```

All provider interaction is inside `backend/app/services/ai_service.py`. It uses the OpenAI Python SDK, Responses API, a Pydantic structured response, a 25-second timeout, no automatic SDK retries, bounded input/output, and `store=False`. See [official Structured Outputs documentation](https://developers.openai.com/api/docs/guides/structured-outputs).

The API receives the selected incident’s service, type, timestamp, threshold, metrics, and up to 30 redacted log excerpts. It has no tools and cannot execute commands or modify infrastructure. Provider timeout, refusal, malformed output, or authentication failure returns a retryable error without substituting demo output. Successful results are persisted and reused; already analyzed incidents are not regenerated when switching providers. Create a new incident to try real AI after a demo analysis.

Only one analysis runs at a time. Real requests are limited to ten attempts per hour, including failures, recorded in PostgreSQL so restart does not reset the limit. API keys never reach the browser. Real API use incurs provider charges; configure your provider project budget separately.

## Tests

Run the full backend suite against an isolated disposable PostgreSQL service (does not touch the application database):

```sh
./scripts/test.sh
```

For local unit-only development with [uv](https://docs.astral.sh/uv/):

```sh
cd backend
uv sync --frozen
uv run pytest -q
uv run ruff check app tests migrations
```

Database tests explicitly skip without `TEST_DATABASE_URL`. To run them locally, set that variable to a dedicated disposable PostgreSQL database whose name contains `test`; its tables are dropped and recreated per test. Never point it at application data.

Frontend production build and browser acceptance tests (requires the running Compose stack in demo AI mode):

```sh
cd frontend
npm ci
npm run build
npx playwright install chromium
npm run test:e2e
```

If downloading Chromium is unavailable and Google Chrome is installed, use `BROWSER_CHANNEL=chrome npm run test:e2e`.

For additional live checks of latency, log-burst, and metrics-unavailability modes, run `python3 scripts/smoke_modes.py` from the project root after browser tests finish. It uses the local demo login (or `ADMIN_PASSWORD`) and verifies conflicts, telemetry-created incidents, expiry, and recovery.

Run `python3 scripts/check_resilience.py` after simulations finish to verify that a Prometheus outage remains unknown (without false service incidents), and that a backend restart preserves incident evidence and saved explanations. It intentionally interrupts local monitoring briefly and restarts Prometheus in a `finally` block.

Browser tests default to the generated demo admin password. For a custom one, set `ADMIN_PASSWORD` in the test environment. Browser tests intentionally create incidents and invoke bounded failures; run them against a local demo. They verify chart data, admin login, HTTP failure detection, evidence, sample AI, recovery, persisted public viewing, and mobile overflow. Screenshots and traces go to ignored `frontend/test-results/`.

Backend coverage includes threshold boundaries, low traffic, missing/non-finite Prometheus values, sustained conditions, startup grace, incident deduplication/recovery/recurrence, log filtering/redaction/delivery deduplication, CSRF/session expiry/login throttling, mocked AI responses/timeouts/refusal, concurrency, and persisted attempt limits.

### Verified locally

The implementation was checked with 53 passing backend tests against PostgreSQL, a successful TypeScript/Vite production build, the complete browser reviewer workflow, and mobile page checks. All four simulation modes produced real incidents and recovered automatically. The outage/restart check verified unknown monitoring state without false incidents and preserved incident evidence and saved analyses across a backend restart. Real OpenAI responses are covered by mocks; a paid API request was not made. Public HTTPS provisioning requires your VM and domain and was not performed locally.

## Deploy to a Linux VM

1. Install Docker Engine and Compose 2.24.4+ on a small Linux VM. A 2-vCPU/4-GB machine is a practical demo starting point; usage varies with retention and traffic.
2. Copy the project; run `python3 scripts/configure.py` without `--demo` and choose a unique admin password.
3. Point your domain’s DNS A/AAAA records at the VM. Open inbound TCP 80/443 (and optionally UDP 443); do not expose database, backend, demo, or Prometheus ports.
4. Edit `.env`: set `SITE_ADDRESS=monitor.example.com`, `PUBLIC_ORIGIN=https://monitor.example.com`, and `COOKIE_SECURE=true`. Keep the origin exact, without a trailing slash. Do not use the local demo password publicly.
5. Run:

```sh
docker compose -f compose.yaml -f compose.production.yaml up -d --build
```

Caddy serves the same-origin frontend/API, obtains HTTPS certificates, redirects HTTP, and stores certificates in a persistent volume. The production override replaces the localhost-only port binding with 80/443. Backend startup rejects insecure public-origin/cookie combinations. Caddy applies a same-origin CSP, frame protection, body limits, and a trusted client-IP header. The backend does not trust arbitrary forwarded headers.

Authentication is one admin account, a PBKDF2 password hash, and an expiring signed HttpOnly/SameSite cookie. Mutations require exact Origin and CSRF checks. Login throttling is per client IP, five attempts per five minutes, held in bounded process memory. Logout clears the browser cookie; rotating `SESSION_SECRET` invalidates all outstanding sessions. There is no registration, password-reset email, or multi-user permission system.

To update, pull/copy the new version and rerun the same Compose command. Startup applies Alembic migrations before serving requests. Back up first when upgrading schemas. This repository does not provision infrastructure or deploy to an external account.

### Backup, restore, and reset

```sh
# Backup the application database without printing credentials.
docker compose exec -T postgres pg_dump -U monitor -d monitor > monitor-backup.sql

# Restore into a NEW empty database or a deliberately reset local environment.
docker compose exec -T postgres psql -U monitor -d monitor < monitor-backup.sql

# DESTRUCTIVE local reset: removes incident history, logs, metrics, and Caddy certificates.
docker compose down --volumes
```

For production, include both Compose files in operational commands. Keep `.env` and database backups private. `/api/health`, Compose health checks, and `docker compose logs` provide basic operational visibility. Prometheus outages appear as **unknown** in the dashboard rather than falsely healthy services.

## Adding another demo service

Add a second demo-service container with a unique `SERVICE_NAME`, the same ingestion and demo-control credentials as configured on the backend. Add its target and matching `service` label to `monitoring/prometheus.yml`. Set backend `SERVICE_URLS` to a JSON map, for example `{"demo-service":"http://demo-service:8001","demo-two":"http://demo-two:8001"}`. Restart Prometheus and backend. The dashboard discovers service names through the summary endpoint. The initial project intentionally ships only one service.

## Interview talking points and boundaries

- Prometheus stores time-series metrics; PostgreSQL stores searchable logs, incidents, and evidence snapshots.
- Deterministic rules decide when to alert. The LLM explains observations and uncertainty; it does not decide whether an incident exists.
- The unique partial index prevents alert storms for a continuing condition; healthy streaks reduce recovery flapping.
- A single FastAPI loop keeps scheduling explainable. One worker is required; distributed scheduling and locks are unnecessary at this scale.
- Bounded buffers, retention, fixed query ranges, and synthetic workloads make the demonstration predictable.
- Public viewing and admin-only actions support portfolio sharing without exposing paid AI or failure controls.
- Deliberate exclusions: Kubernetes, distributed tracing, Kafka, Celery, automated remediation, complex agent frameworks, multi-tenancy, and high-availability guarantees.
