# Security Policy

## Scope

This directory contains an imported Open Notebook snapshot that has been modified and validated as the Intelos Knowledge Engine bootstrap.

The currently supported scope is local, single-user, personal and development use through the canonical Docker Compose configuration.

It is not approved for production, public internet exposure or untrusted multi-user access.

## Supported code state

Security assessment applies to the current Intelos branch and its locked dependencies, not to an upstream Open Notebook release tag or image.

Do not assume that an upstream image, single-container distribution, example Compose file or later upstream release has received the same Intelos validation.

## Reporting a vulnerability

Do not publish exploitable details, credentials, sensitive documents or private logs in a public issue, discussion or pull request.

Use the Intelos repository's private security-reporting capability where available, or contact the repository maintainer directly with the minimum information needed to reproduce and assess the issue.

Include, where relevant:

- affected commit or branch;
- component and endpoint;
- deployment method;
- preconditions and impact;
- minimal reproduction steps using non-sensitive test data;
- relevant sanitised logs;
- suggested remediation.

## Current security model

- protected API routes use a single bearer password;
- missing password configuration fails closed;
- passwordless mode requires `OPEN_NOTEBOOK_ALLOW_NO_AUTH=true` and is intended only for isolated tests;
- provider credentials depend on `OPEN_NOTEBOOK_ENCRYPTION_KEY`;
- host ports are restricted to `127.0.0.1` by the canonical Compose file;
- SurrealDB credentials are mandatory;
- root container execution remains a documented residual risk;
- remote access, production deployment and multi-user operation are not approved.

## Documentation

Review:

- [Docker Compose Installation](docs/1-INSTALLATION/docker-compose.md)
- [Security Configuration](docs/5-CONFIGURATION/security.md)
- [Environment Reference](docs/5-CONFIGURATION/environment-reference.md)
- [Residual Risks](../../docs/security/knowledge-engine-residual-risks.md)

Security controls documented by Intelos take precedence over retained upstream examples and historical material.
