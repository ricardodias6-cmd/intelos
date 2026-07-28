# Environment Reference

This reference describes the Intelos Knowledge Engine configuration used by the canonical Docker Compose deployment.

## Required variables

The checked-in Compose file rejects empty required values.

| Variable | Required | Default in canonical Compose | Purpose |
|---|---:|---|---|
| `OPEN_NOTEBOOK_ENCRYPTION_KEY` | Yes | none | Encrypts stored provider credentials. Losing or changing it makes existing encrypted credentials unreadable. |
| `OPEN_NOTEBOOK_PASSWORD` | Yes | none | Password used by the Web UI and as the bearer credential for protected API routes. |
| `SURREAL_USER` | Yes | none | SurrealDB user created during initial database setup. |
| `SURREAL_PASSWORD` | Yes | none | SurrealDB password created during initial database setup. |

The example file sets `SURREAL_USER=intelos` as a suggested username, but the password remains empty and must be supplied.

## Authentication

| Variable | Default | Description |
|---|---|---|
| `OPEN_NOTEBOOK_PASSWORD` | none | Protected routes fail closed when no password is configured. |
| `OPEN_NOTEBOOK_ALLOW_NO_AUTH` | `false` | Allows passwordless access only when explicitly set to a recognised true value. Use only for isolated tests or local development. |

Missing `OPEN_NOTEBOOK_PASSWORD` does not disable authentication. Protected requests receive a configuration error unless `OPEN_NOTEBOOK_ALLOW_NO_AUTH=true` has been deliberately set.

Docker secret files are supported through:

- `OPEN_NOTEBOOK_PASSWORD_FILE`
- `OPEN_NOTEBOOK_ENCRYPTION_KEY_FILE`

Do not define both the direct value and its `_FILE` variant without verifying the secret-loading precedence.

## Database connection

| Variable | Canonical value | Description |
|---|---|---|
| `SURREAL_URL` | `ws://surrealdb:8000/rpc` | Internal Compose network address. |
| `SURREAL_USER` | required from `.env` | Database user. |
| `SURREAL_PASSWORD` | required from `.env` | Database password. |
| `SURREAL_NAMESPACE` | `open_notebook` | Database namespace. |
| `SURREAL_DATABASE` | `open_notebook` | Database name. |

Database credentials are applied when SurrealDB is first initialised. Editing `.env` later is not a validated credential-rotation procedure for an existing data directory.

## Network and API

| Variable | Default or canonical value | Description |
|---|---|---|
| `API_HOST` | `0.0.0.0` inside the container | Container bind address. Host publication remains restricted to `127.0.0.1` by Compose. |
| `API_PORT` | `5055` | API port. |
| `FRONTEND_BIND_HOST` | `0.0.0.0` inside the container | Frontend bind address inside the container. |
| `API_URL` | auto-detected | External API URL used by the frontend when required. |
| `INTERNAL_API_URL` | internal default | Server-side API route used by the Next.js process. |
| `CORS_ORIGINS` | canonical local origins | Comma-separated origins allowed to call the API. |
| `OPEN_NOTEBOOK_MAX_UPLOAD_SIZE_MB` | `100` | Maximum API request body size in megabytes. |

The distinction between container binding and host publication is important. The processes listen inside the container, while Docker Compose publishes ports only on `127.0.0.1`.

The canonical Compose value is:

```dotenv
CORS_ORIGINS=http://127.0.0.1:8502,http://localhost:8502
```

Do not set `CORS_ORIGINS=*` for an exposed deployment.

## Worker and processing

| Variable | Default | Description |
|---|---|---|
| `OPEN_NOTEBOOK_WORKER_MAX_TASKS` | `5` | Maximum concurrent background tasks. Set to `1` for constrained local hardware or local model servers. |
| `OPEN_NOTEBOOK_EMBEDDING_BATCH_SIZE` | `50` | Number of texts sent in each embedding batch. |
| `OPEN_NOTEBOOK_MIN_CHUNK_SIZE` | `5` | Minimum token count retained for embedding. |
| `API_CLIENT_TIMEOUT` | `300` | Frontend/API client timeout in seconds. |
| `ESPERANTO_LLM_TIMEOUT` | `60` | Language-model request timeout. |
| `ESPERANTO_TTS_TIMEOUT` | `300` | Text-to-speech timeout. |
| `TTS_BATCH_SIZE` | `5` | Concurrent text-to-speech requests. |

## Optional extraction runtimes

These are disabled by default and were not covered by the validated smoke test.

| Variable | Default | Description |
|---|---|---|
| `OPEN_NOTEBOOK_ENABLE_DOCLING` | `false` | Installs the Docling runtime and model dependencies on first startup. |
| `OPEN_NOTEBOOK_ENABLE_CRAWL4AI` | `false` | Installs local Crawl4AI and Chromium components on first startup. |
| `CRAWL4AI_API_URL` | none | Uses a separately managed Crawl4AI service instead of the local runtime. |
| `FIRECRAWL_API_KEY` | none | Firecrawl provider credential. |
| `FIRECRAWL_API_URL` | none | Self-hosted Firecrawl endpoint. |
| `JINA_API_KEY` | none | Jina extraction credential. |

Runtime installation downloads additional packages, models or browsers into caches under `/app/data`. Review supply-chain, resource and licence implications before enabling it.

## Proxy variables

Standard proxy variables are supported:

- `HTTP_PROXY`
- `HTTPS_PROXY`
- `NO_PROXY`

Internal service names must bypass the proxy. The application adds common local and SurrealDB hosts as a safety measure, but explicit configuration is recommended in managed environments.

Example:

```dotenv
NO_PROXY=localhost,127.0.0.1,surrealdb,host.docker.internal
```

Do not place proxy credentials in committed files.

## TLS verification

| Variable | Default | Description |
|---|---|---|
| `ESPERANTO_SSL_VERIFY` | `true` | Validates provider TLS certificates. |
| `ESPERANTO_SSL_CA_BUNDLE` | none | Optional custom CA bundle path. |

Disabling TLS verification is for isolated troubleshooting only and should not become a persistent configuration.

## Observability

LangSmith tracing variables may transmit prompts, responses and metadata to an external service:

- `LANGCHAIN_TRACING_V2`
- `LANGCHAIN_ENDPOINT`
- `LANGCHAIN_API_KEY`
- `LANGCHAIN_PROJECT`

Tracing is not required for normal operation. Review data-handling implications before enabling it.

## Minimal canonical `.env`

```dotenv
OPEN_NOTEBOOK_ENCRYPTION_KEY=<long-random-secret>
OPEN_NOTEBOOK_PASSWORD=<long-random-password>
SURREAL_USER=intelos
SURREAL_PASSWORD=<long-random-password>
```

The remaining database and local CORS values are supplied by the checked-in Compose file.

## Operational rules

- never commit `.env`;
- never use example strings as real secrets;
- restart the affected containers after changing configuration;
- back up the encryption key separately from the database;
- keep host ports bound to localhost;
- do not infer that a green CI run approves remote or production deployment;
- consult [Security Configuration](security.md) and the [Residual Risks](../../../../docs/security/knowledge-engine-residual-risks.md).
