# Quick Start: External Ollama

Use this route when Ollama is installed directly on the same computer that runs Docker.

## 1. Install the Knowledge Engine

Follow [Docker Compose Installation](../1-INSTALLATION/docker-compose.md).

Use the checked-in Intelos Compose file and local application build.

## 2. Install and start Ollama

Install Ollama through its official distribution channel, download the required language and embedding models, and verify the local endpoint:

```bash
curl --fail http://127.0.0.1:11434/api/version
```

Keep the Ollama service limited to the local computer unless remote access has been separately reviewed.

## 3. Reach the host from Docker

On Docker Desktop for macOS and Windows, configure the provider URL as:

`http://host.docker.internal:11434`

On Linux, add a local Compose override:

```yaml
services:
  open_notebook:
    extra_hosts:
      - "host.docker.internal:host-gateway"
```

Then use the same provider URL:

`http://host.docker.internal:11434`

## 4. Configure the provider

In the Web UI:

1. add an Ollama provider configuration;
2. enter the host URL above;
3. test the connection;
4. discover and register the installed models;
5. assign language and embedding defaults.

## 5. Troubleshoot

Test connectivity from the application container:

```bash
docker compose exec open_notebook \
  curl --fail http://host.docker.internal:11434/api/version
```

When the request fails, check the host firewall, Ollama process and host-gateway mapping. Keep the service local while troubleshooting.

## Scope

External Ollama was not included in the validated Knowledge Engine smoke test. Model behaviour, GPU access, licences and resource use remain outside the current validation scope.
