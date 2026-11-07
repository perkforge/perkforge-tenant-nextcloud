# Protected Nextcloud tenant

Read README.md and docs/physical-deployment.md before changes. Big Bang/Flux is
the active platform; bundles/ and prior HANDOFF/operations evidence describe a
historical Fleet/VM trial, not an active physical deployment path. Enrollment Git
owns namespaces, quotas, RBAC, admission/network policies and source registration.
This repository owns only namespaced app resources and values. Do not add security
foundations here. No public exposure or household-data import.

Never commit secrets or browser state. Never delete PVCs, the CNPG Cluster or
namespaces, uninstall/reset/rebuild, format disks or overwrite data without
explicit action-specific approval and verified backup. Review/pin application
revisions in enrollment Git. Do not commit, push or run tests without user
authorization. Draft-PR preparation authorizes offline tests and feature-branch
publication only; it does not authorize merge, release or live activation.

## Working rules

- Use the GitHub CLI (`gh`) for PerkForge GitHub operations unless Corey directs otherwise. Do not switch tools or credentials to bypass an access denial.
- Use the [Current Board](https://github.com/orgs/perkforge/projects/1/views/1) as authoritative for work scope, priority and status. Check the relevant issue before starting or proposing the next task.
- Keep tickets and PR/MR descriptions concise: outcome, blocker or next action, and relevant evidence links. Avoid repeated narration.
- Work on feature branches and submit draft PRs/MRs for Corey to review and merge. Never commit or push directly to main, merge, or enable auto-merge on his behalf.
- Prefer one cohesive PR/MR and coordinated deployment per app when practical. Preserve required repository boundaries and safety/approval stages; link dependent PRs/MRs.
- For authorized changes, run relevant local/offline tests and checks before handoff, even while CI is disabled or paused. Report passed, failed and unrun checks. Offline validation never authorizes live changes.
