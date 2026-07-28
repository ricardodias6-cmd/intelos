# Single Container Installation

## Intelos status: unsupported

The upstream Open Notebook single-container images are not an approved installation route for Intelos.

They are excluded because they:

- bypass the locally reviewed Intelos source build;
- use external mutable application images;
- bundle the application and database into a less transparent runtime;
- were not covered by the Intelos dependency validation or smoke test;
- retain deployment assumptions that conflict with the current fail-closed authentication and localhost-only scope.

Do not deploy:

- `lfnovo/open_notebook:v1-latest-single`;
- `ghcr.io/lfnovo/open-notebook:v1-latest-single`;
- any equivalent upstream single-container image as a substitute for the Intelos service.

Use the supported [Docker Compose Installation](docker-compose.md), which builds `intelos-knowledge-engine:local` from this repository and runs SurrealDB as a separate service.

A future single-container distribution would require its own Dockerfile review, dependency audit, image scan, authentication validation, persistence test and documented upgrade procedure before it could be supported.
