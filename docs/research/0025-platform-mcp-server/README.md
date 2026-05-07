# Decision 0025 — LINQ Platform MCP Server (V1): research folder

**Status:** ADR drafted as Proposed (2026-05-06).
**Date:** 2026-05-06
**ADR:** [`docs/decisions/0025-platform-mcp-server.md`](../../decisions/0025-platform-mcp-server.md)

## What this folder contains

| File | Purpose |
|---|---|
| [`README.md`](README.md) | This file — landing page, reading order. |
| [`deep-dives/v1-auth-and-dispatch-research.md`](deep-dives/v1-auth-and-dispatch-research.md) | Foundational research arc grounding the V1 design. Eight findings on AWS SSO identity, API Gateway IAM auth, SigV4 signing, DynamoDB schema, the MCP protocol surface, cross-account resource policies, caller-principal extraction, and TypeScript Lambda + DynamoDB read patterns. Each finding cites verbatim source quotes. |
| `implementation-plan.md` | Phase 2.3 deliverable. Authored after the ADR is approved. Ordered task list mapping the decision into the `platform-mcp-server-hackathon` repo and the `linq-erp-dev` AWS account. |

The ADR itself is the canonical decision record. This folder is the durable explanation of *why* and *what was researched* for operators reading it later.

## Reading order

1. Start with the ADR: [`docs/decisions/0025-platform-mcp-server.md`](../../decisions/0025-platform-mcp-server.md). Locks the decision and the implementation contract.
2. If you want to verify the architectural choices against authoritative sources, read [`deep-dives/v1-auth-and-dispatch-research.md`](deep-dives/v1-auth-and-dispatch-research.md). It is the source-cited foundation behind every binding choice in the ADR.
3. The implementation plan lands here once the ADR is approved.

## Cross-references

- Implementation repo: [`github.com/shannoncarver/platform-mcp-server-hackathon`](https://github.com/shannoncarver/platform-mcp-server-hackathon) — the empty repo where all V1 code will be authored.
- ERP product handler: deploys to the `linq-erp-dev` AWS account.
