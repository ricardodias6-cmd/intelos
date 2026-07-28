# From Source Installation

This route is for contributors and local development. The validated deployment route remains [Docker Compose](docker-compose.md).

## Prerequisites

- Python 3.12
- Node.js 22
- Git
- Docker with Docker Compose for SurrealDB
- `uv`

Use the versions defined by the repository and CI rather than older upstream version ranges.

## 1. Open the imported service

From the Intelos repository:

```bash
cd services/knowledge-engine
```

Do not clone or substitute the upstream Open Notebook repository when validating Intelos changes.

## 2. Create the environment file

```bash
cp .env.example .env
```

Define every required value:

```dotenv
OPEN_NOTEBOOK_ENCRYPTION_KEY=<long-random-secret>
OPEN_NOTEBOOK_PASSWORD=<long-random-password>
SURREAL_USER=intelos
SURREAL_PASSWORD=<long-random-password>
```

The application fails closed when the password is missing. Passwordless access is available only through `OPEN_NOTEBOOK_ALLOW_NO_AUTH=true` for isolated tests or local development and should not be part of the normal setup.

## 3. Install locked dependencies

```bash
uv sync --frozen
cd frontend
npm ci
cd ..
```

Do not replace locked installation commands with unpinned package installation unless intentionally updating dependencies and lockfiles.

## 4. Start SurrealDB

Use the canonical Compose service:

```bash
docker compose up -d surrealdb
```

The database port remains bound to `127.0.0.1:8000`.

## 5. Start the API

```bash
API_HOST=127.0.0.1 API_RELOAD=true \
  uv run --env-file .env uvicorn api.main:app \
  --host 127.0.0.1 --port 5055 --reload
```

## 6. Start the worker

In another terminal:

```bash
uv run --env-file .env \
  surreal-commands-worker --import-modules commands
```

For constrained local hardware:

```bash
OPEN_NOTEBOOK_WORKER_MAX_TASKS=1 \
  uv run --env-file .env \
  surreal-commands-worker --import-modules commands --max-tasks 1
```

## 7. Start the frontend

In another terminal:

```bash
cd frontend
HOSTNAME=127.0.0.1 PORT=8502 npm run dev
```

Open:

`http://127.0.0.1:8502`

## 8. Verify

```bash
curl --fail http://127.0.0.1:5055/health
```

Confirm that a protected API request without credentials returns `401` and that the Web UI requires the configured password.

## Quality checks

Backend:

```bash
uv run ruff check .
uv run pytest
```

Frontend:

```bash
cd frontend
npm run lint
npm test -- --run
npm run build
```

Dependency audits:

```bash
uv run pip-audit
cd frontend
npm audit --omit=dev --audit-level=high
```

The GitHub Actions workflows remain the authoritative integration validation.

## Network safety

Keep development servers on localhost. Do not bind development reload servers to all interfaces or expose them through a reverse proxy.

## Cleanup

```bash
docker compose down
```

This preserves the database directory. Remove data only after creating and verifying a backup or when deliberate data loss is acceptable.
