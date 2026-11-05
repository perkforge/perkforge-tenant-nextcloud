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
