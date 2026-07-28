# Connection Issues

This guide applies to the canonical local Intelos Docker Compose deployment.

## Expected local endpoints

- Web UI: `http://127.0.0.1:8502`
- API: `http://127.0.0.1:5055`
- SurrealDB diagnostics: `http://127.0.0.1:8000`

The host ports should remain bound to localhost.

## Check service state

```bash
docker compose ps
docker compose logs --no-color
```

The application container includes the API, worker and frontend. There are not separate Compose services named `api` or `frontend` in the canonical stack.

## Check API health

```bash
curl --fail http://127.0.0.1:5055/health
```

Expected response:

```json
{"status":"healthy"}
```

When this fails, inspect:

```bash
docker compose logs open_notebook
docker compose logs surrealdb
```

The API retries the initial database connection and runs migrations before becoming ready.

## Check the Web UI

```bash
curl --fail http://127.0.0.1:8502/
```

The frontend waits for the API during container startup. A healthy API may appear before the frontend is ready, so allow additional startup time.

## Authentication responses

A protected request without credentials should return `401`:

```bash
curl --output /dev/null --write-out '%{http_code}\n' \
  http://127.0.0.1:5055/api/notebooks
```

If it returns `503`, verify that `OPEN_NOTEBOOK_PASSWORD` is configured. Authentication fails closed when the password is missing.

## Port conflict

Identify the local process using the port, or change only the host-side port while keeping the localhost address:

```yaml
ports:
  - "127.0.0.1:8503:8502"
```

Recreate the stack:

```bash
docker compose up -d
```

Do not remove the `127.0.0.1` prefix as a connectivity workaround.

## Database connection failure

Confirm that the application and database use the same values from `.env` and that the internal URL remains:

```dotenv
SURREAL_URL=ws://surrealdb:8000/rpc
```

The host-side database port does not change the internal Compose address.

If the database was previously initialised with different credentials, editing `.env` alone may not rotate them. Consult the database guide before changing or deleting persisted data.

## Proxy-related failures

A configured system or corporate proxy may intercept the SurrealDB WebSocket connection. Ensure local and internal service names bypass the proxy:

```dotenv
NO_PROXY=localhost,127.0.0.1,surrealdb,host.docker.internal
```

Do not share proxy credentials in logs or issue reports.

## Local Ollama connection

For Ollama on the host, use `host.docker.internal` as described in the [External Ollama Guide](../0-START-HERE/quick-start-external-ollama.md).

Keep Ollama local. Do not publish it broadly to solve container connectivity.

## Timeouts

Check resource use and logs before increasing timeouts:

```bash
docker stats
docker compose logs open_notebook
```

For overloaded local model servers, reduce worker concurrency:

```dotenv
OPEN_NOTEBOOK_WORKER_MAX_TASKS=1
```

## Remote or reverse-proxy access

Remote access is outside the approved Intelos scope. Do not change the API URL to a LAN address, expose ports on all interfaces or add public firewall rules as a troubleshooting step.

Restore the canonical local configuration and consult the [Reverse Proxy Decision Record](../5-CONFIGURATION/reverse-proxy.md).

## Related guidance

- [Quick Fixes](quick-fixes.md)
- [Docker Compose Installation](../1-INSTALLATION/docker-compose.md)
- [Database Configuration](../5-CONFIGURATION/database.md)
- [Security Configuration](../5-CONFIGURATION/security.md)
