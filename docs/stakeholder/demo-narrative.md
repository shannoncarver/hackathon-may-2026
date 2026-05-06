# Demo Narrative: ERP User Authorization Debug
 
**Use case:** A LINQ Technical Specialist investigates why a district user cannot log in to ERP.
 
---
 
## The Problem
 
A support ticket comes in. A district administrator cannot access ERP. The Technical Specialist knows the answer lives somewhere across Auth0 and the ERP authorization records — but pulling those threads manually means figuring out who has access to what, documenting what they know, and waiting on someone else to look it up. On a busy day, that wait is hours. The district is blocked.
 
This is the problem the skills solve.
 
---
 
## What the Hackathon Demo Shows
 
The live demo intentionally focuses on two skills to demonstrate the core pattern cleanly within the time available: the Auth0 Management skill and the ERP Verify User Authorization skill. Together they answer the most common version of this support scenario — is this user set up correctly on both ends of the auth flow?
 
This is not the full extent of what was built. It is a deliberate, minimized scope chosen to make the workflow legible in a short window. The full incident-triage chain is documented separately in the Tutorials section.
 
---
 
## What the Engineer Does
 
The engineer opens Claude Code and describes the issue in plain language:
 
> "A user at this district can't log in to ERP. Can you help me figure out why?"
 
No commands. No system knowledge required. Claude reads the available skills, selects the right ones, and begins the investigation.
 
---
 
## What Happens
 
**Step 1 — Auth0 check**
 
Claude invokes the Auth0 Management skill. It queries the user's account status, recent log events, and app client configuration using a read-only machine-to-machine client scoped to logs and user data. This surfaces whether the account is locked, misconfigured, or missing an expected app assignment.
 
**Step 2 — ERP authorization check**
 
Claude invokes the ERP Verify User Authorization skill. It queries the DynamoDB authorization table using the user's email and the tenant ID passed in. It checks whether a direct user record exists for that tenant, and whether a superuser record covers the user regardless of tenant.
 
---
 
## The Result
 
The skill returns a structured finding:
 
- **Authorization status:** Authorized (via superuser record)
- **Tenant record:** Not found for the ID provided
- **Root cause:** The tenant ID passed in is missing the required `ALO32` prefix. The actual tenant record exists under the correctly prefixed ID.
- **Recommended action:** Rerun the check using the correctly formatted tenant ID, or update the reference in the system that generated the original ID.
This is the kind of finding that gets missed in a manual investigation. The user would have appeared authorized at first glance, but the downstream tenant mismatch would have caused the login to fail anyway. The skill caught it, explained it, and pointed to the fix.
 
The engineer did not escalate. They did not wait. They had an answer and a next step in under a minute.
 
---
 
## The Full Picture: Incident Triage Chain
 
The two-skill demo is a focused entry point into a broader workflow. The complete incident-triage chain covers five skills end-to-end:
 
1. **Auth0 log retrieval** — surfaces recent events and account state
2. **Auth0 security and AWS-side state** — checks configuration and posture
3. **Harmony Auth debug** — validates AWS-side Harmony Auth configuration
4. **ERP Verify User Authorization** — confirms DynamoDB authorization records
5. **Knowledge wiki ingest** — saves the resolved case so the next engineer starts with context
The full chain is documented in the Tutorials section of this site under Incident Triage. Each skill also has its own standalone walkthrough for engineers who need to run a single step in isolation.
 
---
 
## What We Do Not Show
 
- Live queries against real district user accounts or production systems
- Harmony Auth as a live demo step — it is built and documented in the Tutorials section, but excluded from the demo to keep the workflow legible in five minutes
- Invented metrics: no fabricated ticket resolution times, Auth0 log counts, or authorization record volumes
---
 
## Known Gaps
 
The demo proves the pattern works. It also surfaces what a production-ready version would still need:
 
**Tenant resolution** — The engineer had to know the correct tenant ID format to get a clean result. A tenant resolution skill that maps a human-readable tenant name to the correct system ID would remove that dependency entirely.
 
**Centralized credential management** — Each skill currently relies on local environment configuration (AWS SSO profiles, `.env` files). A production setup would route credential lookup through the Platform Services AWS account so engineers run the skills without any manual setup.
 
Both gaps are known and scoped. They represent the next layer of work after the Hackathon.
 
---
 
## Repeatable by Design
 
When the engineer closes the ticket, they save the case to the knowledge wiki. The next time a similar issue comes in, that resolution is already available as context for Claude. The system compounds over time. Every ticket closed makes the next investigation faster.
