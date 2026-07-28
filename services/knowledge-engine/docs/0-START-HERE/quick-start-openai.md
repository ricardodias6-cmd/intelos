# Quick Start: OpenAI

This guide assumes that the canonical Intelos Docker Compose stack is already running.

Do not create a separate Compose file and do not use an upstream `lfnovo/open_notebook:*` image.

## 1. Install the base service

Follow [Docker Compose Installation](../1-INSTALLATION/docker-compose.md).

Confirm that:

- the Web UI is available at `http://127.0.0.1:8502`;
- the API health endpoint returns `{"status":"healthy"}`;
- you can sign in with `OPEN_NOTEBOOK_PASSWORD`.

## 2. Obtain an OpenAI API key

Create the key through the official OpenAI platform and store it in a password manager. Do not place provider keys in the repository or in screenshots, logs or issue reports.

Provider pricing and model availability change over time. Check the provider's current documentation before selecting a model.

## 3. Add the credential

In the Web UI:

1. open the credential or model settings;
2. add an OpenAI credential;
3. paste the API key;
4. save and test the connection;
5. discover and register the required models.

The credential is encrypted using `OPEN_NOTEBOOK_ENCRYPTION_KEY` before storage.

## 4. Assign models

Select suitable defaults for:

- language generation;
- embeddings;
- optional speech or other capabilities used by your workflow.

Start with low-volume test content and review provider costs before processing large document sets.

## 5. Verify

Create a disposable notebook, add a small text source and run a simple chat or transformation.

Do not use sensitive operational content until you have reviewed what data the selected cloud provider receives and accepted the applicable privacy and retention terms.
