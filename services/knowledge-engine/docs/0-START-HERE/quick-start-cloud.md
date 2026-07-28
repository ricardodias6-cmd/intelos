# Quick Start: Cloud AI Providers

This guide covers Anthropic, Google, Groq, OpenRouter, Mistral and other supported cloud providers after the Intelos Knowledge Engine has been installed.

## 1. Install the base service

Follow [Docker Compose Installation](../1-INSTALLATION/docker-compose.md).

Use the checked-in Compose file, mandatory secrets and localhost-only port bindings. Do not copy upstream Compose examples or use mutable upstream application images.

## 2. Obtain a provider credential

Create a key through the provider's official account portal and store it securely.

Before using sensitive content, review:

- what source text is sent to the provider;
- provider data retention and training settings;
- account region and contractual terms;
- rate limits and current pricing;
- whether the selected model supports the required capability.

## 3. Add the credential

In the Web UI:

1. open the credential or model settings;
2. choose the provider;
3. enter the provider credential and any required endpoint;
4. save and test the connection;
5. discover and register models.

Stored provider credentials depend on `OPEN_NOTEBOOK_ENCRYPTION_KEY`. Keep that key backed up securely and separate from database backups.

## 4. Assign models

Select default models for the capabilities you intend to use, especially language generation and embeddings.

A provider may offer language models but not embeddings, speech or other features. Mixed-provider configurations are supported, but each credential must be reviewed separately.

## 5. Verify with disposable content

Create a temporary notebook, add a short non-sensitive source and run a small request.

Confirm that:

- the request succeeds;
- the expected model is used;
- costs and rate-limit behaviour are acceptable;
- errors do not reveal credentials.

Provider names, model identifiers, prices and limits change frequently. Treat old examples as illustrative and consult current provider documentation.
