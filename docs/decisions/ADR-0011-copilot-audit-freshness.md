# ADR-0011 — Copilot audit linkage and evidence freshness

- Status: Accepted
- Date: 2026-07-30
- Decision owners: Intelos Evidence Core

## Context

The Copilot already returns an answer, an answer identifier, and an audit report
identifier. The audit report must also identify the exact conversation turn that
produced it and must remain useful after document maintenance changes the
evidence graph.

Document versions are immutable, but their lifecycle can move from current to
superseded or revoked. A previously validated answer must therefore be checked
against the current lifecycle state when its audit report is queried.

## Decision

The AuditReport records:

- conversation_id and turn_id for Copilot turns;
- response_mode (default, concise, detailed, or audit);
- a freshness object with a status, revalidation flag, affected Evidence IDs,
  related document-change identifiers, reason, and check timestamp.

Freshness is evaluated from the selected Evidence IDs, their document versions,
and matching document_change records:

- current means no known maintenance event affects the selected evidence;
- possibly_outdated means a referenced version was modified or superseded;
- outdated means a referenced version was revoked;
- unknown means an evidence or version record is unavailable.

Possibly_outdated, outdated, and unknown always require revalidation. The
system never silently regenerates or presents a stale factual answer. It returns
the existing answer with its audit metadata so the client can require review or
start the established reprocessing flow.

The existing non-Copilot evidence endpoint remains compatible: its reports use
response_mode=default and omit optional conversation identifiers.

## Consequences

Audit queries perform a bounded freshness check against the selected evidence
and maintenance tables. The persisted report keeps the last stored snapshot,
while the query response reflects the current version/revocation state. This
avoids treating a stale persisted boolean as authoritative.

The contract is deliberately additive, so reports written before migration 31
remain readable with safe defaults.
