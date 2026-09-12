# Aksara v0.7.1 — Documentation & Developer Experience

Aksara v0.7.1 makes the project's public documentation and developer experience
match actual installed behavior. It introduces no new runtime capability and no
intentional runtime semantic or dependency change.

## Public truth and onboarding

- Rebuilt onboarding and Quick Start around an installed package and PostgreSQL.
- Added one progressive Ticket Desk learning path covering models, migrations,
  generated REST, identity, permissions, tenancy, tasks, Durable Operations,
  reporting, and optional MCP.
- Corrected configuration, deployment, production, recovery, and upgrade
  guidance.
- Documented Durable Operations as the user-facing capability introduced in
  v0.7.0, including its authorization, transaction, retry, approval,
  cancellation, and external-effect boundaries.
- Improved bundled examples, generated-project README instructions, scaffold
  guidance, and CLI help.
- Clarified Stable, Evolving, and Experimental surfaces.
- Populated the public roadmap from the post-v0.7 capability and market review.

## Executable documentation

Public Python snippets, JSON examples, CLI forms, scaffold flows, retained
examples, the Ticket Desk tutorial, and documentation links are compiled,
executed, parsed, or validated by the release gates. Installed-wheel journeys
exercise the final distribution independently of the source checkout.

## Release boundary

This release contains no new runtime capability, no intentional runtime semantic
change, no dependency change, and no schema or migration change. The v0.7.1
documentation audit disclosed 22 functional findings. Those findings remain
documented and deliberately unfixed here; each requires separate maintenance
work and review.
