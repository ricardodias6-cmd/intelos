# Local Development Setup

This guide describes the supported local development workflow for the Intelos Knowledge Engine import.

## Scope

Development occurs inside `services/knowledge-engine` in the Intelos repository.

The imported upstream repository, images and Compose examples are not substitutes for this source tree.

## Toolchain

Use the versions exercised by CI:

- Python 3.12
- Node.js 22
- `uv`
- Docker with Docker Compose
- Git

## Environment

```bash
cd services/knowledge-engine
cp .env.example .env
```

Fill every required value:

```dotenv
OPEN_NOTEBOOK_ENCRYPTION_KEY=<long-random-secret>
OPEN_NOTEBOOK_PASSWORD=<long-random-password>
SURREAL_USER=intelos
SURREAL_PASSWORD=<long-random-password>
```

Do not commit `.env`.

Authentication fails closed when the password is absent. `OPEN_NOTEBOOK_ALLOW_NO_AUTH=true` is reserved for controlled tests or isolated local development and must not become a normal developer default.

## Locked dependencies

```bash
uv sync --frozen
cd frontend
npm ci
cd ..
```

Use `uv sync` without `--frozen` or a package-manager update command only when deliberately changing dependencies and lockfiles.

## Database

Start only the canonical SurrealDB service:

```bash
docker compose up -d surrealdb
```

This preserves the checked-in localhost port binding and required credentials.

Do not start an independent database with example `root` credentials.

## API

```bash
uv run --env-file .env uvicorn api.main:app \
  --host 127.0.0.1 --port 5055 --reload
```

The API runs migrations during startup and fails if the database cannot be reached or migrated.

Verify:

```bash
curl --fail http://127.0.0.1:5055/health
```

Expected response:

```json
{"status":"healthy"}
```

## Background worker

The worker is required for source processing, embeddings and other asynchronous jobs:

```bash
uv run --env-file .env \
  surreal-commands-worker --import-modules commands
```

For constrained hardware or local model servers:

```bash
OPEN_NOTEBOOK_WORKER_MAX_TASKS=1 \
  uv run --env-file .env \
  surreal-commands-worker --import-modules commands --max-tasks 1
```

## Frontend

```bash
cd frontend
npm run dev -- --hostname 127.0.0.1 --port 8502
```

Open `http://127.0.0.1:8502` and sign in with `OPEN_NOTEBOOK_PASSWORD`.

## Authentication checks

Unauthenticated protected request, expected status `401`:

```bash
curl --output /dev/null --write-out '%{http_code}\n' \
  http://127.0.0.1:5055/api/notebooks
```

Authenticated request:

```bash
curl --fail \
  --header "Authorization: Bearer ${OPEN_NOTEBOOK_PASSWORD}" \
  http://127.0.0.1:5055/api/notebooks
```

Avoid exposing secrets through shared shell history or logs.

## Backend quality checks

```bash
uv run ruff check .
uv run pytest
```

The Python dependency audit is performed by the authoritative GitHub Actions workflow against the locked virtual environment.

## Frontend quality checks

```bash
cd frontend
npm run lint
npm test
npm run build
npm audit --omit=dev --audit-level=high
```

## Container validation

When changing the Dockerfile, Compose file, startup scripts or dependencies:

```bash
docker compose config
docker compose build open_notebook
docker compose up -d
```

Run the smoke test path before merging changes that affect runtime behaviour.

## Development rules

- bind reload servers to localhost;
- do not publish SurrealDB beyond localhost;
- do not replace the local build with an upstream image;
- do not use imported example Compose files as production parity;
- preserve locked dependency installs;
- keep optional Docling and Crawl4AI runtimes disabled unless the change specifically concerns them;
- use disposable non-sensitive data in tests;
- rely on GitHub Actions as the final integration gate.

## Stopping services

Stop manually started API, worker and frontend processes, then run:

```bash
docker compose down
```

This preserves the existing data directories.

## Further reading

- [From Source Installation](../1-INSTALLATION/from-source.md)
- [Testing](testing.md)
- [Security](security.md)
- [Residual Risks](../../../../docs/security/knowledge-engine-residual-risks.md)
