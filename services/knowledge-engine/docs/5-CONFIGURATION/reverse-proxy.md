# Reverse Proxy and Remote Access

## Intelos status: not approved

The imported upstream nginx, Caddy, Traefik and cloud-platform examples are not approved deployment instructions for the Intelos Knowledge Engine.

The validated scope is local access through ports bound to `127.0.0.1`.

## Why the old examples were removed

The former examples could encourage users to:

- replace the locally audited build with a mutable upstream image;
- publish the Web UI or API to a LAN or the internet;
- rely on a single shared bearer password as the only remote access control;
- expose services without a validated rate-limit, monitoring or incident-response design;
- treat HTTPS termination as sufficient production hardening.

Those assumptions conflict with the current residual-risk assessment.

## Current rule

Keep the canonical Docker Compose bindings:

```yaml
ports:
  - "127.0.0.1:8502:8502"
  - "127.0.0.1:5055:5055"
```

Keep SurrealDB on:

```yaml
ports:
  - "127.0.0.1:8000:8000"
```

Do not add router port forwarding, unrestricted firewall rules, a public DNS record or a public reverse proxy for this service.

## Requirements for a future remote deployment

Remote access must be designed and reviewed as a separate change. At minimum, it requires:

1. TLS with managed certificates and secure protocol configuration.
2. Network restriction through a VPN, private access gateway or explicit allowlist.
3. Stronger authentication, preferably an identity-aware proxy with individual accounts and multi-factor authentication.
4. Rate limiting and protection against repeated authentication attempts.
5. Restricted `CORS_ORIGINS` using exact HTTPS origins.
6. Secure secret storage and documented credential rotation.
7. Centralised logs, monitoring and an incident-response process.
8. Backup, restore and recovery testing.
9. Container and operating-system vulnerability scanning.
10. Removal of root runtime privileges and least-privilege volume permissions.
11. Pinned container-image provenance and an SBOM.
12. A review of every external AI, extraction and tracing provider.

## Internal proxy architecture

The frontend can proxy browser API requests to the FastAPI service. This technical capability does not constitute approval for remote deployment.

A future reviewed design should normally expose only the frontend through the access gateway and keep the API and SurrealDB on private networks. Direct API exposure must have a separate use case, authentication design and access policy.

## CORS

For local operation, the canonical Compose file uses:

```dotenv
CORS_ORIGINS=http://127.0.0.1:8502,http://localhost:8502
```

A future remote deployment must replace this with the exact approved HTTPS origin. A wildcard is not acceptable.

## API URL configuration

`API_URL`, `INTERNAL_API_URL` and forwarded-host headers may be required by a future reverse-proxy design. They should be configured only after the proxy topology is defined and tested.

Do not use these variables to work around incorrect public port exposure.

## Decision record

Until a dedicated remote-access pull request completes the controls above and passes security validation, this page serves as a prohibition and requirements record rather than a deployment tutorial.

See:

- [Security Configuration](security.md)
- [Environment Reference](environment-reference.md)
- [Residual Risks](../../../../docs/security/knowledge-engine-residual-risks.md)
