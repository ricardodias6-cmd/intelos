# Advanced Configuration

Advanced settings must preserve the local and fail-closed security posture of the canonical Intelos deployment.

## Worker concurrency

The worker defaults to five concurrent tasks.

For constrained hardware or local model servers:

```dotenv
OPEN_NOTEBOOK_WORKER_MAX_TASKS=1
```

Increase concurrency only after observing memory, CPU, model-server limits and database behaviour under representative workloads.

## Embedding batches

```dotenv
OPEN_NOTEBOOK_EMBEDDING_BATCH_SIZE=50
OPEN_NOTEBOOK_MIN_CHUNK_SIZE=5
```

Reduce the batch size when a local or strict provider cannot handle the default request size.

## Timeouts

```dotenv
API_CLIENT_TIMEOUT=300
ESPERANTO_LLM_TIMEOUT=60
ESPERANTO_TTS_TIMEOUT=300
```

Set the client timeout higher than the longest expected provider operation. Increasing a timeout does not resolve provider rate limits, stalled workers or unavailable services.

## TTS concurrency

```dotenv
TTS_BATCH_SIZE=5
```

Lower the value for local or rate-limited providers.

## Ports

Canonical host bindings:

- Web UI: `127.0.0.1:8502`
- API: `127.0.0.1:5055`
- SurrealDB: `127.0.0.1:8000`

When changing a host port, preserve the localhost address:

```yaml
ports:
  - "127.0.0.1:8503:8502"
```

Do not shorten this to `8503:8502`, because that may publish the service on every host interface.

Changing the host-side SurrealDB port does not change the internal Compose address. The application should normally continue using:

```dotenv
SURREAL_URL=ws://surrealdb:8000/rpc
```

## CORS

Canonical local origins:

```dotenv
CORS_ORIGINS=http://127.0.0.1:8502,http://localhost:8502
```

Add another local origin only when the frontend is deliberately moved to another local port. Do not use a wildcard as a troubleshooting shortcut.

## TLS verification

```dotenv
ESPERANTO_SSL_VERIFY=true
```

Use `ESPERANTO_SSL_CA_BUNDLE` for an approved private certificate authority. Disabling verification should be temporary, isolated and documented.

## Proxy configuration

Standard variables are supported:

```dotenv
HTTP_PROXY=http://proxy.example:8080
HTTPS_PROXY=http://proxy.example:8080
NO_PROXY=localhost,127.0.0.1,surrealdb,host.docker.internal
```

A proxy may receive provider traffic and metadata. Review its trust, logging and credential-handling policy.

## Tracing

LangSmith tracing can transmit prompts, responses and execution metadata to an external service.

Leave it disabled unless deliberately needed:

```dotenv
LANGCHAIN_TRACING_V2=false
```

Do not enable tracing for sensitive content without an explicit data-handling review.

## Optional extraction runtimes

```dotenv
OPEN_NOTEBOOK_ENABLE_DOCLING=false
OPEN_NOTEBOOK_ENABLE_CRAWL4AI=false
```

Enabling either runtime downloads additional packages, models or browsers during startup. These paths were not covered by the current smoke test.

## Debug logging

Verbose logs may include document names, provider errors, URLs or other operational data. Use debug logging only for the minimum time required and review logs before sharing them.

## Unsupported tuning assumptions

The Intelos documentation does not treat the following as supported advanced configuration:

- remote server exposure;
- public reverse proxies;
- multi-user scaling;
- shared SurrealDB tenancy;
- production resource sizing;
- copied upstream Compose examples;
- mutable external application images.

Those scenarios require separate design, security and operational validation.

See:

- [Environment Reference](environment-reference.md)
- [Security Configuration](security.md)
- [Residual Risks](../../../../docs/security/knowledge-engine-residual-risks.md)
