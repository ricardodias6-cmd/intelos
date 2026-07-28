# Developer Guide

Development takes place inside the Intelos repository at:

`services/knowledge-engine`

Do not clone the upstream Open Notebook repository as a substitute for this imported and hardened snapshot.

## Supported development setup

Follow:

- [From Source Installation](docs/1-INSTALLATION/from-source.md)
- [Development Quick Start](docs/7-DEVELOPMENT/quick-start.md)
- [Development Setup](docs/7-DEVELOPMENT/development-setup.md)

## Minimum local sequence

```bash
cd services/knowledge-engine
cp .env.example .env
# Fill every required secret in .env
uv sync --frozen
cd frontend && npm ci && cd ..
docker compose up -d surrealdb
```

Start the API, worker and frontend only on localhost, as described in the development guide.

## Validation

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

The GitHub Actions workflows remain authoritative for integration validation.

## Security constraints

- `OPEN_NOTEBOOK_PASSWORD` is required for the normal development setup.
- Missing authentication fails closed.
- `OPEN_NOTEBOOK_ALLOW_NO_AUTH=true` is limited to isolated tests.
- Do not use default SurrealDB credentials.
- Do not bind reload servers to external interfaces.
- Do not copy upstream Compose examples over the canonical Intelos file.
