# Docker Compose Installation

This is the canonical installation method for the Intelos Knowledge Engine.

It builds the application from the repository, requires explicit secrets and limits published ports to the local machine.

## Scope

The configuration is approved only for local, single-user, personal and development use.

It is not approved for public internet exposure or production deployment. Review the [residual risks](../../../../docs/security/knowledge-engine-residual-risks.md) before use.

## Prerequisites

- Docker Desktop or Docker Engine with Docker Compose
- Git
- a terminal with access to the repository

## 1. Open the service directory

```bash
cd services/knowledge-engine
```

## 2. Create `.env`

```bash
cp .env.example .env
```

Fill every required value. Docker Compose deliberately rejects empty values.

Example structure:

```dotenv
OPEN_NOTEBOOK_ENCRYPTION_KEY=<long-random-secret>
OPEN_NOTEBOOK_PASSWORD=<long-random-password>
SURREAL_USER=intelos
SURREAL_PASSWORD=<long-random-password>
```

Generate random values with a trusted password manager or, where available:

```bash
openssl rand -hex 32
openssl rand -base64 32
```

Do not commit `.env`, print its contents into CI logs or reuse production credentials.

## 3. Validate the resolved configuration

```bash
docker compose config
```

Confirm that:

- no required variable is empty;
- ports `8000`, `8502` and `5055` are bound to `127.0.0.1`;
- the application uses `build:` and the local image `intelos-knowledge-engine:local`;
- no `lfnovo/open_notebook:*` image is present.

## 4. Build the application image

```bash
docker compose build open_notebook
```

The Dockerfile builds the frontend and backend from the checked-in source and locked dependencies.

## 5. Start the stack

```bash
docker compose up -d
```

The stack contains:

- `surrealdb`, bound to `127.0.0.1:8000`;
- `open_notebook`, exposing the Web UI at `127.0.0.1:8502` and the API at `127.0.0.1:5055`.

Inside the application container, supervisord starts the API, worker and frontend.

## 6. Verify startup

```bash
docker compose ps
curl --fail http://127.0.0.1:5055/health
```

Expected API response:

```json
{"status":"healthy"}
```

Open:

`http://127.0.0.1:8502`

Sign in with the value of `OPEN_NOTEBOOK_PASSWORD`.

## 7. Verify authentication

A protected route must reject an unauthenticated request:

```bash
curl --output /dev/null --write-out '%{http_code}\n' \
  http://127.0.0.1:5055/api/notebooks
```

Expected status:

```text
401
```

A valid bearer password should succeed:

```bash
curl --fail \
  --header "Authorization: Bearer ${OPEN_NOTEBOOK_PASSWORD}" \
  http://127.0.0.1:5055/api/notebooks
```

Run this command from a shell in which the password is already exported. Avoid adding secrets to shell history.

## 8. Configure models

In the Web UI:

1. add a provider credential;
2. test the connection;
3. discover and register models;
4. select default language and embedding models.

Provider credentials are encrypted with `OPEN_NOTEBOOK_ENCRYPTION_KEY`. Back up that key securely and separately from database backups.

## Data persistence

The canonical Compose file uses bind mounts:

- `./surreal_data:/mydata`
- `./notebook_data:/app/data`

A normal stop does not delete those directories:

```bash
docker compose down
```

Starting again should preserve the database:

```bash
docker compose up -d
```

Before deleting either directory, create and verify a backup. Backup and restore procedures have not yet been validated as part of the current smoke test.

## Updating the service

The application image is built locally. Do not use `docker compose pull` as the application update process.

After updating the repository:

```bash
docker compose down
docker compose build open_notebook
docker compose up -d
```

Review dependency changes, migrations and release notes before rebuilding.

## Logs and diagnostics

```bash
# All services
docker compose logs -f

# Application only
docker compose logs -f open_notebook

# Database only
docker compose logs -f surrealdb
```

## Port conflicts

Keep the host side bound to localhost when changing a port:

```yaml
ports:
  - "127.0.0.1:8503:8502"
```

Do not change the binding to `8502:8502` or `0.0.0.0:8502:8502` without a separate network security review.

## Authentication failure on startup

The application fails closed when authentication is not configured. Confirm that `.env` contains a non-empty `OPEN_NOTEBOOK_PASSWORD` and restart:

```bash
docker compose up -d
```

`OPEN_NOTEBOOK_ALLOW_NO_AUTH=true` is intended only for isolated tests or local development and is not enabled by the canonical Compose file.

## Database credentials

SurrealDB credentials are established when the database is first initialised. Changing only the values in `.env` does not constitute a validated credential-rotation procedure for an existing database.

Do not delete `surreal_data` merely to apply new credentials unless data loss is intended and a verified backup exists.

## Network exposure

The current deployment should remain local.

Do not:

- publish the Web UI or API directly to a LAN or the internet;
- publish SurrealDB beyond localhost;
- add a reverse proxy for remote access;
- rely on the single bearer password as enterprise authentication.

Remote deployment requires TLS, restricted CORS, secure secret management, rate limiting, monitoring, backup and recovery controls, and a new security review.
