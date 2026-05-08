# Demo Narrative: ERP User Authorization Debug

**Use case:** A LINQ Technical Specialist investigates why a district user cannot log in to ERP.

---

## The Problem

A support ticket comes in. A district administrator cannot access ERP. The Technical Specialist knows the answer lives somewhere across Auth0 and the ERP authorization records, but pulling those threads manually means figuring out who has access to what, documenting what they know, and waiting on someone else to look it up. On a busy day, that wait is hours. The district is blocked.

Underneath that pain is a broader platform problem: every team building AI tools at LINQ rebuilds the same auth, credential, and permission infrastructure. This is the problem Platform Services MCP solves.

---

## What the Hackathon Demo Shows

The live demo focuses on two tools registered to Platform Services MCP to demonstrate the core pattern cleanly within the time available: the Auth0 Management tool and the ERP Verify User Authorization tool. Together they answer the most common version of this support scenario, which is whether a user is set up correctly on both ends of the auth flow.

This is a deliberate, minimized scope chosen to make the workflow legible in a short window. The full incident-triage chain is documented separately in the Tutorials section.

---

## What the Engineer Does

The engineer opens Claude Code and describes the issue in plain language:

> "A user at this district can't log in to ERP. Can you help me figure out why?"

No commands. No system knowledge required. No per-tool credential setup. Claude routes the request through Platform Services MCP, which authenticates the engineer using their existing AWS SSO session, checks per-user permissions for the requested tools, and orchestrates the investigation.

---

## What Happens

**Step 1: Auth0 check**

Platform Services MCP routes the call to the Auth0 Management tool. The tool retrieves credentials from AWS Parameter Store, with no local config required by the engineer, then queries the user's account status, recent log events, and app client configuration. This surfaces whether the account is locked, misconfigured, or missing an expected app assignment.

**Step 2: ERP authorization check**

Platform Services MCP routes the call to the ERP Verify User Authorization tool, which executes in a separate AWS account. The platform handles cross-account access through Cognito and a JWT authorizer, with no per-tool credential setup required. The tool queries the DynamoDB authorization table using the user's email and the tenant ID passed in. It checks whether a direct user record exists for that tenant, and whether a superuser record covers the user regardless of tenant.

**Step 3: Live permission change**

While the demo is in progress, the team revokes the engineer's permission for the ERP tool directly in DynamoDB. The next call to the tool returns blocked. No redeploy. No service restart. The Permission Engine enforced the change on the next invocation.

Throughout the demo, every call (including the blocked one) is captured by the platform's audit emitter: caller email, tool, decision, latency. The structured JSON is written to CloudWatch and is queryable for any investigation after the fact.

---

## The Result

The investigation returns a structured finding:

- **Authorization status:** Authorized (via superuser record)
- **Tenant record:** Not found for the ID provided
- **Root cause:** The tenant ID passed in is missing the required `ALO32` prefix. The actual tenant record exists under the correctly prefixed ID.
- **Recommended action:** Rerun the check using the correctly formatted tenant ID, or update the reference in the system that generated the original ID.

This is the kind of finding that gets missed in a manual investigation. The user would have appeared authorized at first glance, but the downstream tenant mismatch would have caused the login to fail anyway. The platform caught it, explained it, and pointed to the fix.

The engineer did not escalate. They did not wait. They had an answer and a next step from one prompt.

---

## The Full Picture: Incident Triage Chain

The two-tool demo is a focused entry point into a broader workflow. The complete incident-triage chain covers five tools end-to-end:

1. **Auth0 log retrieval:** surfaces recent events and account state
2. **Auth0 security and AWS-side state:** checks configuration and posture
3. **Harmony Auth debug:** validates AWS-side Harmony Auth configuration
4. **ERP Verify User Authorization:** confirms DynamoDB authorization records
5. **Knowledge wiki ingest:** saves the resolved case so the next engineer starts with context

The full chain is documented in the Tutorials section of this site under Incident Triage. Each tool also has its own standalone walkthrough for engineers who need to run a single step in isolation.

---

## What We Do Not Show

- Live queries against real district user accounts or production systems
- Harmony Auth as a live demo step. It is built and documented in the Tutorials section, but excluded from the demo to keep the workflow legible in five minutes.
- Invented metrics. No fabricated ticket resolution times, Auth0 log counts, or authorization record volumes.

---

## Known Gaps

The demo proves the pattern works. It also surfaces what a production-ready version would still need:

**Tenant resolution.** The engineer had to know the correct tenant ID format to get a clean result. A tenant resolution tool that maps a human-readable tenant name to the correct system ID would remove that dependency entirely.

**OAuth-based MCP install.** Engineers currently install Platform Services MCP via a per-machine AWS Signature V4 shim. The longer-term direction is OAuth, matching where the MCP spec is heading.

**Auth0 as the platform-layer identity provider.** The platform currently uses AWS-native auth at the entry point. Migrating to Auth0 would align the platform with where the MCP spec is going and consolidate identity across LINQ.

These gaps are known and scoped. They represent the next layer of work after the Hackathon.

---

## Repeatable by Design

When the engineer closes the ticket, they save the case to the knowledge wiki. The next time a similar issue comes in, that resolution is already available as context for Claude. The system compounds over time. Every ticket closed makes the next investigation faster.

The platform itself is also repeatable. Any LINQ team that registers a tool to Platform Services MCP gets the same authentication, credential management, permission enforcement, and audit trail without rebuilding any of it. The login failure investigation is the first proof case. It is not the only one.
