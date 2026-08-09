# Document control

| Field | Value |
|---|---|
| Product | FastDataGov |
| Document set | Open-source functional, architecture, implementation and transition specification |
| Version | 0.1 (implementation baseline) |
| Status | Maintained |
| Product author | FastSME / Predictive Labs Ltd |
| Technical reviewers | Project maintainers and deploying organisation architecture/security owners |
| Business reviewers | Deploying organisation governance lead, data owners and stewards |
| License | MIT |
| Last reviewed | 2026-08-09 |

## Version and approval process

Code releases use semantic versions in `pyproject.toml` and `CHANGELOG.md`. Material architecture, security, data-model, adapter-contract or operating-model changes require a pull request, passing verification, a changelog entry and review under `CONTRIBUTING.md`. Deploying organisations record local design authority and security approval in their own change system; this repository never implies customer approval.

## Controlled related documents

- `README.md` — product and deployment entry point.
- `docs/ARCHITECTURE.md` — system boundaries and design decisions.
- `docs/COMPLETION_MATRIX.md` — functional release gate.
- `docs/IMPLEMENTATION_GUIDE.md` — discovery through transition.
- `docs/PILOT_RUNBOOK.md` — generic Snowflake-first pilot and measures.
- `docs/OPERATIONS_RUNBOOK.md` — day-two operation and recovery.
- `docs/TRAINING_AND_TRANSITION.md` — role-based enablement and handover.
- `docs/CAPABILITY_MATRIX.md` — platform capability boundaries.
- `SECURITY.md` — security posture and vulnerability reporting.

Commercial proposals, ROI responses and customer-specific architecture are deliberately outside this public, generic repository.
