# Configuration

This section documents the Intelos Knowledge Engine configuration that accompanies the canonical local Docker Compose deployment.

## Required configuration

Create `.env` from `.env.example` and define:

```dotenv
OPEN_NOTEBOOK_ENCRYPTION_KEY=<long-random-secret>
OPEN_NOTEBOOK_PASSWORD=<long-random-password>
SURREAL_USER=intelos
SURREAL_PASSWORD=<long-random-password>
```

All four controls are required by the canonical Compose file. Empty values make Compose fail.

Authentication does not become optional when the application password is missing. Protected routes fail closed unless `OPEN_NOTEBOOK_ALLOW_NO_AUTH=true` is explicitly enabled for an isolated test.

## Configuration areas

### [Environment Reference](environment-reference.md)

Authoritative variables, defaults and operational rules for the Intelos import.

### [Database](database.md)

Canonical SurrealDB connection, credential and persistence guidance.

### [Security](security.md)

Authentication behaviour, secret handling, network limits and residual controls.

### [Advanced](advanced.md)

Performance, worker concurrency, timeouts and safe local port changes.

### [AI Providers](ai-providers.md)

Provider configuration through the Web UI. Provider credentials are encrypted with `OPEN_NOTEBOOK_ENCRYPTION_KEY`.

### [Ollama](ollama.md)

Local model-provider guidance. The Ollama runtime itself remains outside the validated Knowledge Engine smoke-test scope.

### [Reverse Proxy](reverse-proxy.md)

Current Intelos decision record. Remote access is not approved under the local bootstrap scope.

## Canonical local values

The checked-in Compose file supplies:

```dotenv
SURREAL_URL=ws://surrealdb:8000/rpc
SURREAL_NAMESPACE=open_notebook
SURREAL_DATABASE=open_notebook
CORS_ORIGINS=http://127.0.0.1:8502,http://localhost:8502
```

The host publishes the Web UI, API and SurrealDB only on `127.0.0.1`.

Do not replace these bindings with unrestricted ports merely to resolve a connectivity problem.

## AI provider setup

After the local service is running:

1. sign in with `OPEN_NOTEBOOK_PASSWORD`;
2. add a provider credential in the Web UI;
3. test the connection;
4. discover and register models;
5. assign default language and embedding models.

Do not place provider keys in `.env` unless a specifically supported provider integration requires it. Avoid secrets in logs, screenshots and issue reports.

## Unsupported assumptions removed from the import

The Intelos configuration no longer treats these as valid defaults:

- database user and password `root`;
- missing application authentication;
- public host port bindings;
- mutable upstream application images;
- remote server or public reverse-proxy deployment;
- copying an imported example over the canonical Compose file.

## Scope

The current configuration is for local, single-user, personal and development use. It is not production-ready.

Review:

- [Docker Compose Installation](../1-INSTALLATION/docker-compose.md)
- [Residual Risks](../../../../docs/security/knowledge-engine-residual-risks.md)
