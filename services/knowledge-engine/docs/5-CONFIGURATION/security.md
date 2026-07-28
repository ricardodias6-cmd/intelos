# Security Configuration

This page describes the security posture of the Intelos Knowledge Engine import.

## Approved scope

The current deployment is approved only as a local, single-user bootstrap for personal use and development.

It is not approved for:

- public internet exposure;
- untrusted LAN access;
- multi-user operation;
- production workloads;
- sensitive operational data without a separate risk assessment.

The complete residual-risk record is maintained at:

`../../../../docs/security/knowledge-engine-residual-risks.md`

## Mandatory secrets

The canonical Docker Compose deployment requires:

```dotenv
OPEN_NOTEBOOK_ENCRYPTION_KEY=<long-random-secret>
OPEN_NOTEBOOK_PASSWORD=<long-random-password>
SURREAL_USER=intelos
SURREAL_PASSWORD=<long-random-password>
```

Empty values make Compose fail. Do not use example values, reuse passwords or commit `.env`.

## Authentication behaviour

Protected API routes require a bearer password:

```http
Authorization: Bearer <OPEN_NOTEBOOK_PASSWORD>
```

Authentication fails closed:

- a configured password protects all non-excluded routes;
- a missing password does not make the API public;
- a missing password returns a service-configuration error;
- passwordless mode requires the explicit setting `OPEN_NOTEBOOK_ALLOW_NO_AUTH=true`.

Passwordless mode is intended only for isolated tests or local development. It is not enabled by the canonical Compose file.

Publicly accessible routes include the health endpoint and API schema routes required for local operation and diagnostics. Do not treat this as proof that the deployment is safe for remote exposure.

## Limitations of the password model

The current control is basic access protection, not an enterprise identity system.

It does not provide:

- individual user accounts;
- role-based permissions;
- single sign-on;
- session expiry policies;
- rate limiting;
- account lockout;
- audit logging;
- native TLS termination.

The same password is used as a bearer credential. Anyone who obtains it can call protected API routes.

## Provider credential encryption

Provider credentials stored by the application depend on `OPEN_NOTEBOOK_ENCRYPTION_KEY`.

Operational rules:

- keep the key secret;
- back it up separately from database backups;
- do not rotate it by simply replacing the value;
- understand that losing or changing it makes existing encrypted credentials unreadable;
- use a separate key for each deployment.

Docker secret files are supported through `OPEN_NOTEBOOK_PASSWORD_FILE` and `OPEN_NOTEBOOK_ENCRYPTION_KEY_FILE`.

## Network controls

The canonical Compose file publishes:

- Web UI on `127.0.0.1:8502`;
- API on `127.0.0.1:5055`;
- SurrealDB on `127.0.0.1:8000`.

Keep those localhost bindings.

Do not replace them with unrestricted host bindings, open firewall rules or router port forwarding.

The application and frontend processes listen on container interfaces so that Docker networking works. This does not mean the host ports should be exposed externally.

## CORS

The canonical local setting is:

```dotenv
CORS_ORIGINS=http://127.0.0.1:8502,http://localhost:8502
```

Do not use a wildcard for an exposed deployment. CORS is not an authentication control and does not replace TLS, network filtering or identity management.

## SurrealDB

The database is reachable by the application over the internal Compose network and is published to localhost only for local diagnostics.

Important limitations:

- the container currently runs as root;
- the image is referenced by a mutable major-version tag;
- changing `.env` credentials after initialisation is not a validated rotation procedure;
- backup, restore and abrupt-failure recovery are not yet validated.

Do not expose port `8000` beyond localhost.

## Containers and privileges

The `open_notebook` and SurrealDB containers currently run with root privileges. `no-new-privileges` is enabled, but this does not remove root inside the container.

This is the highest residual production risk and is accepted only for the local bootstrap scope.

Before production use, redesign the runtime so that:

- optional dependencies are not installed at startup;
- dedicated non-root users own only the required paths;
- volume permissions follow least privilege;
- the final image is scanned and supplied with an SBOM;
- base images are pinned and updated through a controlled process.

## Optional runtimes

Docling and local Crawl4AI are disabled by default. Enabling them downloads additional packages, models or browsers at startup.

They were not covered by the current smoke test and increase the runtime and supply-chain surface.

## Cloud providers and telemetry

Using a cloud model, extraction provider or tracing service may transmit document content, prompts, responses or metadata outside the local machine.

Before enabling any provider:

- review its privacy and retention terms;
- verify account and project settings;
- use non-sensitive test content first;
- understand which application features send data externally;
- avoid placing credentials in logs or screenshots.

LangSmith tracing is optional and may transmit detailed request data. Leave it disabled unless deliberately required.

## Reverse proxies and remote access

The imported upstream reverse-proxy examples are not approved deployment instructions for Intelos.

Remote access requires a new security review covering at least:

- TLS termination and certificate management;
- network allowlisting or VPN access;
- stronger authentication or an identity-aware proxy;
- rate limiting;
- secure secret storage and rotation;
- restricted CORS;
- monitoring and audit records;
- backup, restore and incident recovery;
- image and operating-system vulnerability scanning.

See [Reverse Proxy](reverse-proxy.md) for the current Intelos status.

## Verification commands

Health check:

```bash
curl --fail http://127.0.0.1:5055/health
```

Unauthenticated protected request, expected status `401`:

```bash
curl --output /dev/null --write-out '%{http_code}\n' \
  http://127.0.0.1:5055/api/notebooks
```

Authenticated request:

```bash
curl --fail \
  --header "Authorization: Bearer ${OPEN_NOTEBOOK_PASSWORD}" \
  http://127.0.0.1:5055/api/notebooks
```

Avoid exposing the password through shared shell history or logs.

## Security reporting

Do not publish credentials, private data or exploitable vulnerability details in a public issue. Record the minimum reproducible information through the repository's private security-reporting route or contact the maintainer directly.
