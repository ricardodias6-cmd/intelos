# Installation Guide

## Supported installation route

The supported and validated installation method for the Intelos Knowledge Engine is:

[Docker Compose](docker-compose.md)

It builds the application from the checked-in Intelos source, requires explicit secrets and binds the Web UI, API and database ports to localhost.

## Validated scope

The current validation covers:

- Ubuntu Linux x86_64 in GitHub Actions;
- Docker Compose with separate SurrealDB and application containers;
- image build from this repository;
- API and frontend startup;
- password authentication;
- database migrations;
- creation and persistence of a notebook after a clean restart.

This is a local development and personal-use bootstrap. It is not described as production-ready.

## Other installation routes

### From source

[From Source](from-source.md) is available for contributors and development. It requires explicit authentication and database credentials and should bind development services to localhost unless a separate network security review has been completed.

### Single container

[Single Container](single-container.md) is not supported for the Intelos import. The imported upstream image instructions bypass the locally audited build and are retained only as historical context.

### Native Windows

[Native Windows](windows-native.md) has not been validated for Intelos. Windows users should use Docker Desktop and the canonical Docker Compose route.

## Requirements

- Docker Desktop or Docker Engine with Docker Compose;
- Git;
- at least 4 GB of available RAM, with 8 GB or more recommended;
- sufficient disk space for containers, database files and imported content;
- an AI provider credential, unless using a local provider such as Ollama.

## Before installation

Read:

- [Environment Reference](../5-CONFIGURATION/environment-reference.md)
- [Security Configuration](../5-CONFIGURATION/security.md)
- [Residual Risks](../../../../docs/security/knowledge-engine-residual-risks.md)

Do not use default passwords, publish the service on all network interfaces or replace the local build with a mutable upstream image.
