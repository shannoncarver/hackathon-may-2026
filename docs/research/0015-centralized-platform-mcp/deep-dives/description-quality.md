# Deep dive — tool descriptions as the routing function

**Status:** Educational / further reading. Not part of the formal review record.
**For:** [Decision 0015 — Centralized Platform MCP Server](../../../decisions/0015-centralized-platform-mcp.md). Backed by review artifacts in [`docs/research/0015-centralized-platform-mcp/`](../00-overview.md).
**Date:** 2026-05-04

This document explains why MCP tool descriptions deserve the same engineering rigor as a public HTTP API contract, what makes a description good or bad for LLM callers, what the platform's `mcp-handler-lint` enforces, and how to handle semantic collisions across product teams. It expands on review risk **R12** in [`03-risks-register.md`](../03-risks-register.md) and finding **12** in [`role-passes/mcp-integration.md`](../role-passes/mcp-integration.md).

## Why descriptions are not docstrings

The LLM that calls an MCP tool sees only three things per entry: `name`, `description`, and `inputSchema` ([`mcp-tool-catalog`](../../../../knowledge/wiki/entities/mcp-tool-catalog.md)). It does not see the handler's code, its registry binding, its IAM policy, its tests, or its owners. Two consequences follow:

1. **The description is the routing function.** When a user prompt could match more than one tool, the model picks the one whose `name + description` best matches the prompt's intent. Change the description, you've changed which prompts route to the handler — even if the code is unchanged.
2. **Description quality has a blast radius.** A vague description silently steals invocations from a more specific tool, or gets skipped entirely. Either failure surfaces to the human user as "the AI is broken."

This is why **description quality is operational discipline**, not editorial polish. The platform-team-owned style guide and CI lint exist because cross-product description drift is the single highest-leverage cause of tool-selection error at fleet scale.

## The bad-vs-good contrast

### Bad description — common first draft

```json
{
  "name": "erp.checkUserAccess",
  "description": "Checks if a user has access in ERP."
}
```

What's wrong:

- **No safety signal.** Nothing says read-only. The model can't reason about whether to call this in a write-cautious context.
- **No returns clause.** "Checks if" is vague — boolean? role list? error envelope? The model has to guess.
- **No disambiguation.** If `crm.checkUserAccess` exists, a prompt like *"is alice authorized?"* with no product mentioned will route to either tool by chance.
- **No input mention.** The description doesn't surface that `tenantId` is required for the answer to make sense.

### Good description — written like an API contract for LLM callers

```json
{
  "name": "erp.checkUserAccess",
  "description": "Read-only. Returns whether a user has access to the LINQ ERP product for a specific tenant, plus the user's role assignments (e.g., 'admin', 'viewer'). Inputs: user email and tenant slug. Use this when verifying ERP entitlement before reading ERP data. Do NOT use this for general user profile lookups (see iam.lookupUser) or for CRM access checks (see crm.checkUserAccess). P50 ~180ms."
}
```

What changed and why:

| Element | Why it's there |
|---|---|
| **`Read-only.` prefix** | Explicit safety signal. Lets the model reason about side-effect risk; lets the platform enforce the `sideEffects: "read"` gate. The MCP spec's `readOnlyHint` annotation is *untrusted* per spec, so the description is the canonical user-facing signal. |
| **`Returns ...` clause** | The shape of the answer. Drives selection (the model reaches for the tool that returns what it needs) and enables the model to compose a confident reply. |
| **`Inputs: ...` clause** | Plain-English shadow of the schema. The model first scans descriptions during tool selection, then reads the schema for shape. Surfacing inputs in the description supports the first pass. |
| **`Use this when ... Do NOT use this for ...`** | The single most under-used pattern in MCP descriptions, and the highest-leverage one. Cross-references to neighbor tools defang ambiguous prompts. |
| **Latency hint (`P50 ~180ms`)** | Lets the model decide whether to chain calls or ask the user to wait. Costs ~10 tokens; saves multi-second user-perceived latency on chained reads. |

The "good" version is roughly 70 tokens longer than the bad one. At 200 handlers, naïve full-catalog injection of richer descriptions adds ~14k tokens to every agent's context. That cost is what makes **server-side `tools/list` projection by authenticated principal** non-optional in the design (see review risk **R4** in [`03-risks-register.md`](../03-risks-register.md), and finding 9 in [`role-passes/mcp-integration.md`](../role-passes/mcp-integration.md)). With projection, agents only load the slice they're authorized for, so paying for richer descriptions on the tools that *are* loaded is the right trade.

## What `mcp-handler-lint` enforces

The lint is policy-as-code on the registry write path (per onboarding step 4 in [`role-passes/platform.md`](../role-passes/platform.md)). It runs in CI on the product team's PR before the registry write goes through. Description-related rules:

| Rule | Rationale |
|---|---|
| Description must start with `Read-only.` (V1) or `Write.` / `Destructive.` (V2+) | Forces explicit safety signal. Gates the `sideEffects: "read"` enforcement check at registration. |
| Description length 80–500 characters | Floor forces substance; ceiling bounds context cost. Per-agent catalog payload is held under ~30k tokens by combining this ceiling with server-side projection. |
| Contains a `Returns ...` clause (verbs: `Returns`, `Lists`, `Looks up`, `Finds`) | The model picks tools partly by what they return. Missing this clause is the dominant cause of skipped invocations in catalogs we've seen. |
| Every `required` field in `inputSchema` is named in description text | Forces description ↔ schema parity. Catches drift when a team adds a required field but forgets to update the description. |
| If a semantic neighbor exists, the description must contain `Use this ...` OR `Do NOT use this ...` | Disambiguates against neighbor tools (see semantic-collision section below). |
| **Banned phrases — substrate leakage:** `Lambda`, `Step Function`, `ECS`, `DynamoDB`, `Calls`, `Internal use of` | Substrate is invisible to agents per the design (the `handlerType` leaky-abstraction concern in [`role-passes/architecture.md`](../role-passes/architecture.md) concern 4). Lint enforces. |
| **Banned phrases — marketing copy:** `Powerful`, `Robust`, `Easy-to-use`, `Comprehensive`, `Best-in-class` | Content-free. Lint refuses it. |
| `description` and `title` must not be identical | Forces actual content. Catches the "I'll fix this later" placeholder. |
| First sentence ≤ 200 chars | The model's selection signal is dominated by the first sentence; long compound first sentences degrade selection accuracy. |

The lint runs against the full registry-item shape, not just the description, but the description-rule subset is the load-bearing one for selection behavior.

## Semantic-collision detection

Per-product prefixes solve **name** collisions: `erp.checkUserAccess` and `crm.checkUserAccess` cannot both register the same `name`. They do **not** solve **description** collisions — both teams could independently write "Checks if a user has access," and the model, given an ambiguous prompt without product context, will guess.

The lint handles this with a semantic-neighbor check at registration time:

1. For each registered tool, compute an embedding of its description (any production-grade embedding model — `text-embedding-3-small` is sufficient at this scale).
2. Cache embeddings in the registry so the lint doesn't recompute on every PR.
3. On a registry write, compute the new tool's embedding and find the top-3 most similar tools by cosine similarity.
4. If any neighbor's similarity exceeds a threshold (~0.85, tunable), require both descriptions to contain explicit disambiguating language (`Use this when ...`, `Do NOT use this for ...`) referencing each other by name.
5. The lint refuses the write until both descriptions land cleanly. This becomes a **two-team PR conversation**, not a one-team merge.

The platform-team review gate in [`role-passes/platform.md`](../role-passes/platform.md) onboarding step 7 fires on exactly this case — semantic collision is one of the narrow exception classes that triggers human review rather than blocking on policy-as-code alone, because resolving it benefits from a neutral facilitator.

## Description-as-versioned-contract

Treat description changes the same way you'd treat a public API change. Practical implications:

- **Bump the registry version.** A meaningful description change (one that alters which prompts route to the handler) is a `1.2.0 → 1.3.0` event, not a silent edit. Pinned agents stay on the old description; rollback is one `LABEL#stable` repoint per the registry schema.
- **Run a description eval before promoting `LABEL#stable`.** A small fixed prompt set (10 must-invoke + 10 must-not-invoke) gives the team a regression signal. If selection accuracy on the must-invoke set drops below 95%, hold the promotion. (A separate deep dive can specify the eval framework end-to-end.)
- **Test descriptions with prompts you didn't write.** The team that authored the handler is not its caller. Have a peer team's engineer or a non-engineer stakeholder write the eval prompts. The author's prompt set is over-fit to the description by definition.
- **Pin descriptions on day one.** Don't ship with a placeholder ("we'll improve it later"). The first 100 invocations set user expectations of what the tool does. A later improvement doesn't retroactively help those 100 sessions.
- **Prefer "do NOT use" over "use only when".** The model is more reliable at avoiding negative patterns than conforming to positive ones. `Do NOT use this for general user profile lookups` is more reliably honored than `Use this only for ERP entitlement checks`.

## Why this lives at the platform layer

A product team with 5 handlers writing descriptions in isolation can produce 5 perfectly good descriptions. The same team with 50 handlers, over time as engineers rotate, will produce inconsistent descriptions. Four product teams independently will produce four interpretations of "good," and the cross-product semantic collisions become invisible because each team only sees their own catalog.

The platform owns the style guide and the lint precisely because **description quality has cross-product blast radius** while every other handler concern (code, IAM, schemas) is scoped within one product. This is the same argument that drives the centralized-broker design as a whole, applied to one specific operational discipline.

## Quick checklist for a product engineer

When adding or changing a handler's description, walk through:

- [ ] Starts with `Read-only.` (V1).
- [ ] Length 80–500 characters; first sentence ≤ 200.
- [ ] Contains a `Returns ...` clause naming the shape of the answer.
- [ ] Inputs clause names every `required` field from the schema.
- [ ] If similar tools exist, contains `Use this ...` or `Do NOT use this ...` language pointing at them.
- [ ] No substrate leakage (`Lambda`, `Step Function`, `ECS`, `DynamoDB`, etc.).
- [ ] No marketing language.
- [ ] Bumped the registry `version` if the description meaningfully changed.
- [ ] Eval prompts updated and rerun before label promotion.

## Related artifacts

- [`role-passes/mcp-integration.md`](../role-passes/mcp-integration.md) — MCP/AI lens findings on catalog cost and `listChanged` storms.
- [`role-passes/platform.md`](../role-passes/platform.md) — onboarding workflow including the lint gate.
- [`03-risks-register.md`](../03-risks-register.md) — R4 (catalog leak), R11 (`listChanged` storms), R12 (description quality).
- [`knowledge/wiki/entities/mcp-tool-catalog.md`](../../../../knowledge/wiki/entities/mcp-tool-catalog.md) — protocol-level reference for tool catalog shape.
