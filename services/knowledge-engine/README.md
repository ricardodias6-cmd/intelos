# Intelos Knowledge Engine

This directory contains the Open Notebook snapshot imported as the initial Knowledge Engine for Intelos.

The imported code is derived from `lfnovo/open-notebook` at commit `62b071b9172a2c823ddd918e0947a782df63be13` and remains subject to its MIT licence. See `INTELOS_IMPORT.md`, `LICENSE` and the repository third-party notices for attribution.

## Supported scope

The currently validated deployment is a local, single-user bootstrap intended for development and personal use.

It is not approved for production, public internet exposure or untrusted multi-user access. The residual risks are recorded in:

`../../docs/security/knowledge-engine-residual-risks.md`

## Canonical installation

Use the repository code and the checked-in Docker Compose file. Do not replace it with an upstream `lfnovo/open_notebook:*` image or with an example copied from the upstream project.

### Prerequisites

- Docker Desktop or Docker Engine with Docker Compose
- Git
- sufficient disk space for the image, database and imported content

### 1. Create the local environment file

From `services/knowledge-engine`:

```bash
cp .env.example .env
```

Fill every value in `.env`. Empty required values deliberately make Docker Compose fail.

Generate strong random values, for example:

```bash
openssl rand -hex 32
openssl rand -base64 32
```

Required variables:

```dotenv
OPEN_NOTEBOOK_ENCRYPTION_KEY=<long-random-secret>
OPEN_NOTEBOOK_PASSWORD=<long-random-password>
SURREAL_USER=intelos
SURREAL_PASSWORD=<long-random-password>
```

Do not commit `.env`.

### 2. Build and start

```bash
docker compose build open_notebook
docker compose up -d
```

The build uses the Intelos source tree and creates the local image `intelos-knowledge-engine:local`.

### 3. Verify

```bash
curl --fail http://127.0.0.1:5055/health
```

Expected response:

```json
{"status":"healthy"}
```

Open the Web UI at:

`http://127.0.0.1:8502`

Sign in with `OPEN_NOTEBOOK_PASSWORD`.

The default Compose configuration binds the Web UI, API and SurrealDB ports to `127.0.0.1` only.

### 4. Configure an AI provider

After signing in:

1. Open the model or credential settings.
2. Add a provider credential.
3. Test the connection.
4. Discover and register the required models.
5. Assign the default language and embedding models.

Provider secrets are encrypted with `OPEN_NOTEBOOK_ENCRYPTION_KEY`. Losing or changing that key makes existing encrypted credentials unreadable.

## Common commands

```bash
# Show service state
docker compose ps

# Follow logs
docker compose logs -f

# Stop containers without deleting persisted data
docker compose down

# Rebuild after source or dependency changes
docker compose build open_notebook
docker compose up -d
```

Data is stored in the bind-mounted `surreal_data` and `notebook_data` directories.

Do not use `docker compose pull` as the normal Intelos update procedure. The application image is built from this repository.

## Authentication behaviour

Authentication fails closed:

- when `OPEN_NOTEBOOK_PASSWORD` is set, protected API routes require `Authorization: Bearer <password>`;
- when the password is missing, protected routes return a configuration error instead of becoming public;
- passwordless access is permitted only when `OPEN_NOTEBOOK_ALLOW_NO_AUTH=true` is explicitly set for an isolated test or local-development environment.

The checked-in Docker Compose file requires a password and does not enable passwordless access.

## Network exposure

Keep the default localhost bindings.

Do not change ports to `0.0.0.0`, publish the service to a LAN, configure a public reverse proxy or expose the SurrealDB port without a separate security review. The current bearer-password model is basic access control and there is no native TLS, user management, rate limiting or audit logging.

## Optional runtimes

Docling and local Crawl4AI are disabled by default. Enabling them downloads additional components at runtime and has not been included in the validated smoke-test scope.

Relevant variables:

```dotenv
OPEN_NOTEBOOK_ENABLE_DOCLING=true
OPEN_NOTEBOOK_ENABLE_CRAWL4AI=true
```

Enable them only when required and after reviewing the additional resource and supply-chain implications.

## Authoritative documentation

For the Intelos import, these documents take precedence over older upstream examples:

- `docs/1-INSTALLATION/docker-compose.md`
- `docs/5-CONFIGURATION/environment-reference.md`
- `docs/5-CONFIGURATION/security.md`
- `../../docs/security/knowledge-engine-residual-risks.md`

Upstream-oriented examples and historical release material are retained for provenance and development reference only. They are not approved deployment instructions for Intelos.
