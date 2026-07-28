# Imported Docker Compose Examples

## Intelos status: reference only

The files in this directory were imported from the upstream Open Notebook snapshot for provenance and development reference.

They are not approved Intelos deployment configurations and must not be copied over the canonical `services/knowledge-engine/docker-compose.yml`.

The examples may contain one or more of the following incompatible assumptions:

- external mutable `lfnovo/open_notebook:*` images;
- default or example database credentials;
- application authentication that is absent or optional;
- ports published beyond localhost;
- optional services and images not covered by Intelos dependency audits;
- single-container or cloud deployment routes that were not smoke-tested;
- older Python, Node.js or package-installation instructions;
- claims of complete privacy that do not account for model downloads, telemetry or external extraction services.

## Supported alternative

Start from:

[Canonical Docker Compose Installation](../docs/1-INSTALLATION/docker-compose.md)

Add optional services only through a reviewed Compose override that preserves:

- the local `intelos-knowledge-engine:local` build;
- mandatory secrets from `.env`;
- localhost-only host port bindings;
- the existing SurrealDB credentials and data path;
- `no-new-privileges` settings;
- explicit documentation of any additional image, volume and network exposure.

## Example status

| File or directory | Intelos status |
|---|---|
| `docker-compose-dev.yml` | Upstream development reference, not validated against the current Intelos workflow. |
| `docker-compose-full-local.yml` | Unvalidated optional AI and speech stack. |
| `docker-compose-ollama.yml` | Unvalidated Ollama integration. Use the local Ollama guide instead. |
| `docker-compose-speaches.yml` | Unvalidated speech-service integration. |
| `docker-compose-single.yml` | Unsupported single-container route. |
| `easypanel/` | Unsupported public/cloud deployment template. |

`docker-compose-single.yml` and the EasyPanel material must not be used as Intelos installation instructions.

## Review requirements for optional services

Before an example or optional service can become supported, it needs:

1. image provenance and version pinning;
2. dependency and image vulnerability scanning;
3. explicit secret handling;
4. localhost or private-network bindings;
5. authentication and CORS validation;
6. functional and persistence smoke tests;
7. resource and licence documentation;
8. an update and rollback procedure.

See:

- [Local Ollama](../docs/0-START-HERE/quick-start-local.md)
- [External Ollama](../docs/0-START-HERE/quick-start-external-ollama.md)
- [Security Configuration](../docs/5-CONFIGURATION/security.md)
- [Residual Risks](../../../docs/security/knowledge-engine-residual-risks.md)
