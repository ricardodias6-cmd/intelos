# Intelos Knowledge Engine: Start Here

The Knowledge Engine is based on an imported Open Notebook snapshot, but Intelos uses its own hardened local deployment configuration.

## Supported path

The validated route is the checked-in Docker Compose stack in `services/knowledge-engine`.

Start with:

1. [Docker Compose installation](../1-INSTALLATION/docker-compose.md)
2. [Environment reference](../5-CONFIGURATION/environment-reference.md)
3. [Security configuration](../5-CONFIGURATION/security.md)
4. [Residual risks](../../../../docs/security/knowledge-engine-residual-risks.md)

The current scope is local, single-user, personal and development use. It is not approved for public internet exposure or production deployment.

## Choose an AI provider

Install the base stack first, then follow one of these provider-specific guides:

- [OpenAI](quick-start-openai.md)
- [Other cloud providers](quick-start-cloud.md)
- [Local Ollama](quick-start-local.md)
- [Ollama already installed on the host](quick-start-external-ollama.md)

These pages no longer provide independent Docker Compose files. They build on the canonical Intelos configuration so that authentication, local port bindings and mandatory secrets remain consistent.

## What the service provides

- notebooks, sources and notes;
- document and URL ingestion;
- full-text and vector search;
- contextual chat and transformations;
- optional podcast generation;
- support for cloud and local AI providers.

Some optional processing runtimes, external providers and large-content flows were not covered by the validated smoke test. Consult the residual-risk record before relying on them.

## Required local controls

Before starting:

- copy `.env.example` to `.env`;
- define a long random encryption key;
- define a long random application password;
- define non-empty SurrealDB credentials;
- keep all published ports bound to `127.0.0.1`;
- build the application from this repository.

Do not copy upstream deployment examples that use default credentials, public port bindings or `lfnovo/open_notebook:*` images.
