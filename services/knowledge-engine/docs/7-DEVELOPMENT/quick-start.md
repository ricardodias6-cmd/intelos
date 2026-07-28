# Development Quick Start

This guide starts the Knowledge Engine from the Intelos repository for local development.

## Prerequisites

- Python 3.12
- Node.js 22
- `uv`
- Docker with Docker Compose
- Git

## 1. Open the service

```bash
cd services/knowledge-engine
```

Do not clone `lfnovo/open-notebook` for Intelos development. The imported snapshot contains Intelos-specific hardening, tests and dependency locks.

## 2. Create the environment

```bash
cp .env.example .env
```

Set non-empty values for:

```dotenv
OPEN_NOTEBOOK_ENCRYPTION_KEY=<long-random-secret>
OPEN_NOTEBOOK_PASSWORD=<long-random-password>
SURREAL_USER=intelos
SURREAL_PASSWORD=<long-random-password>
```

## 3. Install locked dependencies

```bash
uv sync --frozen
cd frontend
npm ci
cd ..
```

## 4. Start SurrealDB

```bash
docker compose up -d surrealdb
```

## 5. Start the processes

Use separate terminals.

API:

```bash
uv run --env-file .env uvicorn api.main:app \
  --host 127.0.0.1 --port 5055 --reload
```

Worker:

```bash
uv run --env-file .env \
  surreal-commands-worker --import-modules commands
```

Frontend:

```bash
cd frontend
HOSTNAME=127.0.0.1 PORT=8502 npm run dev
```

## 6. Verify

```bash
curl --fail http://127.0.0.1:5055/health
```

Expected response:

```json
{"status":"healthy"}
```

Open `http://127.0.0.1:8502` and sign in with the configured password.

## 7. Run checks

```bash
uv run ruff check .
uv run pytest

cd frontend
npm run lint
npm test -- --run
npm run build
```

## Rules

- keep development services bound to localhost;
- use `npm ci` and `uv sync --frozen` for reproducible installs;
- update lockfiles deliberately when changing dependencies;
- never commit `.env`;
- use `OPEN_NOTEBOOK_ALLOW_NO_AUTH=true` only in isolated tests;
- run the GitHub Actions validation before merging.

For more detail, see [Development Setup](development-setup.md).
