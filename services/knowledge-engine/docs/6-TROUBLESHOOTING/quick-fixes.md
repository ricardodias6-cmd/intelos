# Quick Fixes

These fixes assume the canonical Intelos Docker Compose deployment and localhost-only access.

## Service does not start

```bash
docker compose config
docker compose ps
docker compose logs --no-color
```

Confirm that `.env` contains non-empty values for:

- `OPEN_NOTEBOOK_ENCRYPTION_KEY`
- `OPEN_NOTEBOOK_PASSWORD`
- `SURREAL_USER`
- `SURREAL_PASSWORD`

Empty required values intentionally prevent startup.

## API health check fails

```bash
curl --fail http://127.0.0.1:5055/health
docker compose logs open_notebook
```

Expected response:

```json
{"status":"healthy"}
```

The API may wait for SurrealDB and run migrations during startup. Check both application and database logs before restarting repeatedly.

## Web UI cannot reach the API

```bash
docker compose ps
curl --fail http://127.0.0.1:5055/health
curl --fail http://127.0.0.1:8502/
```

Do not fix this by publishing the API on all network interfaces. The canonical Compose file already maps the required ports to localhost.

## Login fails

Confirm the browser password exactly matches `OPEN_NOTEBOOK_PASSWORD`, then restart after changing `.env`:

```bash
docker compose up -d
```

Protected API routes should return `401` without credentials. Missing password configuration should fail closed rather than disable authentication.

## Port already in use

Change only the host-side port and preserve the localhost address:

```yaml
ports:
  - "127.0.0.1:8503:8502"
```

Then recreate the service:

```bash
docker compose up -d
```

## Provider credential cannot be saved

Check that `OPEN_NOTEBOOK_ENCRYPTION_KEY` is configured and unchanged from the value used to encrypt existing credentials.

Losing or changing the key makes existing encrypted credentials unreadable.

## Provider connection fails

In the Web UI:

1. test the credential;
2. confirm the endpoint and account permissions;
3. verify current model availability and rate limits;
4. use a small non-sensitive request;
5. inspect application logs without sharing secrets.

## Source processing remains pending

The worker must be running inside the application container. Check:

```bash
docker compose logs open_notebook
```

For constrained local models, set:

```dotenv
OPEN_NOTEBOOK_WORKER_MAX_TASKS=1
```

and recreate the service.

## File upload is rejected

The default request-body limit is 100 MB. Confirm the file size and configured value:

```dotenv
OPEN_NOTEBOOK_MAX_UPLOAD_SIZE_MB=100
```

Do not raise the limit without considering available memory, disk space and processing time.

## Database authentication fails after editing `.env`

SurrealDB credentials are established during initial database creation. Editing the variables later is not a validated rotation procedure.

Do not delete `surreal_data` merely to clear the error unless deliberate data loss is acceptable and a verified backup exists.

## Optional extraction engine unavailable

Docling and local Crawl4AI are disabled by default. Enable them only when deliberately required and after reviewing the additional downloads and resource use.

## Remote access or reverse-proxy problem

Remote deployment is not approved in the current Intelos scope. Restore the canonical localhost bindings instead of opening firewall rules or publishing additional ports.

See:

- [Connection Issues](connection-issues.md)
- [Docker Compose Installation](../1-INSTALLATION/docker-compose.md)
- [Security Configuration](../5-CONFIGURATION/security.md)
- [Residual Risks](../../../../docs/security/knowledge-engine-residual-risks.md)
