# Quick Start: Local Ollama

This guide adds a local Ollama provider to the canonical Intelos Knowledge Engine installation.

The Knowledge Engine and SurrealDB must first be installed with the checked-in Docker Compose file.

## 1. Install the base service

Follow [Docker Compose Installation](../1-INSTALLATION/docker-compose.md).

Keep the Web UI, API and SurrealDB ports bound to `127.0.0.1`.

## 2. Run Ollama

Use either:

- an Ollama installation on the host, following [External Ollama](quick-start-external-ollama.md); or
- a separate Ollama container that you add deliberately to the local Compose project.

The Ollama container is not part of the validated Intelos stack. Review its image, network exposure, GPU configuration and model storage before adding it.

A minimal local-only service can be added as a Compose override:

```yaml
services:
  ollama:
    image: ollama/ollama:latest
    ports:
      - "127.0.0.1:11434:11434"
    volumes:
      - ./ollama_models:/root/.ollama
    restart: unless-stopped
```

This tag is mutable and is not covered by the Knowledge Engine dependency audit. Pin and update it through a controlled process where reproducibility is required.

## 3. Download models

Choose models that fit the available memory and hardware. At minimum, most workflows need:

- one language model;
- one embedding model.

For a containerised Ollama service:

```bash
docker compose exec ollama ollama pull <language-model>
docker compose exec ollama ollama pull <embedding-model>
```

Model names and hardware requirements change. Confirm them in current Ollama documentation.

## 4. Configure the provider

In the Knowledge Engine Web UI:

1. add an Ollama credential or provider configuration;
2. use `http://ollama:11434` when Ollama is in the same Compose network;
3. test the connection;
4. discover and register the downloaded models;
5. assign the language and embedding defaults.

## 5. Verify

Use a short, non-sensitive text source and verify ingestion, embedding and chat.

Local inference reduces disclosure to a cloud model provider, but it does not by itself guarantee complete privacy. Review model licences, downloaded artefacts, optional telemetry and any extraction services used by the workflow.

## Resource limits

Local models can consume substantial RAM, VRAM, CPU and disk space. Set `OPEN_NOTEBOOK_WORKER_MAX_TASKS=1` when concurrent processing overwhelms the local model server.
