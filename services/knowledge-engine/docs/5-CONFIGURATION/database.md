# Database Configuration

The Intelos Knowledge Engine uses SurrealDB through the canonical Docker Compose stack.

## Canonical connection

The application container connects over the internal Compose network:

```dotenv
SURREAL_URL=ws://surrealdb:8000/rpc
SURREAL_USER=<value from .env>
SURREAL_PASSWORD=<value from .env>
SURREAL_NAMESPACE=open_notebook
SURREAL_DATABASE=open_notebook
```

The checked-in Compose file requires non-empty database credentials. Do not use `root:root`, `root:password` or other imported example values.

## Host publication

SurrealDB is published only on:

`127.0.0.1:8000`

This host port exists for local diagnostics. The application does not need it because it reaches `surrealdb:8000` through the Compose network.

Do not publish the database on all host interfaces or open it through a firewall, router or public reverse proxy.

## Persistence

Data is stored under:

`./surreal_data`

Stopping containers with:

```bash
docker compose down
```

does not remove this directory.

Do not delete it unless deliberate data loss is acceptable and any required backup has been created and verified.

## Initial credentials and rotation

SurrealDB establishes its root credentials when the data directory is first initialised.

Changing `SURREAL_USER` or `SURREAL_PASSWORD` in `.env` after that point is not a validated rotation procedure. The existing database may continue to expect the original credentials.

A future credential-rotation runbook must cover:

1. authenticated database access with the existing credential;
2. creation or update of the replacement account;
3. application configuration update;
4. restart and functional verification;
5. rollback and recovery;
6. removal of the previous credential only after validation.

## Migrations

The API runs database migrations during startup. Startup fails if the database cannot be reached or if migrations fail.

Inspect application logs:

```bash
docker compose logs open_notebook
```

Do not bypass a migration failure by starting the API against an unknown schema.

## Verification

Check service state:

```bash
docker compose ps
```

Check database logs:

```bash
docker compose logs surrealdb
```

Check API health after migrations:

```bash
curl --fail http://127.0.0.1:5055/health
```

## Multiple deployments

Do not share one SurrealDB instance or data directory between independent Intelos deployments without a separate design and isolation review.

The current validation covers one local application stack and one database namespace. It does not validate multi-user, multi-tenant or shared-database isolation.

## Residual risks

The current database container runs as root, uses a mutable image tag and has not completed backup, restore, abrupt-failure or high-concurrency testing.

See the [Residual Risks](../../../../docs/security/knowledge-engine-residual-risks.md).
