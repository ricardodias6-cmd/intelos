# Native Windows Installation

## Intelos status: not validated

The imported upstream native Windows procedure is not an approved installation route for the Intelos Knowledge Engine.

The current validation covers the canonical Docker Compose stack on Linux x86_64. Native Windows introduces separate package, process, path, permission, service-management and SurrealDB behaviours that have not been tested in this branch.

Windows users should use Docker Desktop and follow:

[Docker Compose Installation](docker-compose.md)

That route preserves:

- the locally built Intelos application image;
- locked Python and JavaScript dependencies;
- mandatory application and database credentials;
- localhost-only port bindings;
- the tested startup, authentication and persistence path.

Do not rely on the former upstream instructions that installed SurrealDB, Python, Node.js and application services independently with older version assumptions.

Native Windows support would require a dedicated compatibility matrix, automated tests, secure service configuration, path and file-upload validation, persistence testing and documented upgrade and rollback procedures.
