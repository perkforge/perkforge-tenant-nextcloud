# Protected Nextcloud tenant

Read README.md and docs/operations.md before changes. The platform repository owns
namespaces, quotas, RBAC, network policy, and Fleet registration. This repository
owns only namespaced application resources. Never commit secrets or browser state.
Never delete PVCs, the CNPG Cluster, namespaces, or run uninstall/reset/rebuild
without explicit action-specific approval and a verified backup. No disk formatting.
No public exposure. Review and pin each application revision in the platform repo.
Do not commit, push, or run tests without user authorization.
