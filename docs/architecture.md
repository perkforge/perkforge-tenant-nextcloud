# Architecture

Home LAN -> approved private route -> existing Traefik node ports 443 -> Nextcloud
ClusterIP -> single Nextcloud pod -> single CNPG PostgreSQL pod, both on cks-worker.
A five-minute non-root CronJob shares the application PVC. Recreate strategy
avoids overlapping application replicas on the RWO volume.

Platform-owned default deny has application-specific exceptions for DNS,
Traefik to app port 80, app/cron to database port 5432, CNPG operator to database
instance-manager port 8000, and database instance-manager to the observed API
service/endpoint on 443/6443. Nextcloud has no general internet egress; app store,
SMTP, federation, external storage, external identity and internet updates are
not enabled. Review additional destinations individually before adding features.
The database API exception is specific to this local cluster and must be
rediscovered on migration. Monitoring remains disabled; logs go to stderr and
are available with kubectl logs, subject to node rotation. No central log or
backup retention is configured.

Nextcloud and cron run as www-data UID/GID 33, with dropped capabilities,
RuntimeDefault seccomp and no privilege escalation. The default tenant service
account has token automount disabled and no application RBAC. CNPG manages its
own service account and instance-manager permissions. Its API access is separate
from Nextcloud. The application GitRepo lives in the dedicated Rancher Fleet workspace
`fleet-home-nextcloud`, with a namespace-scoped Policy requiring the named
deployer and disabling namespace creation. A BundleNamespaceMapping selects
only Home-labeled bundles and maps them to the existing fleet-local/local
cluster. Other platform GitRepos keep their original workspace and policy.
Rancher owns the Fleet workspace namespace. Fleet uses a dedicated deployment service account in the
observed agent namespace cattle-fleet-local-system. It can deploy namespaced
application objects and Helm release Secrets; it cannot edit quotas, policies,
namespace labels, Roles, RoleBindings, or cluster resources, and cannot delete
PVCs or CNPG Clusters. This account still has significant authority within this
tenant, including Secrets and controller creation. It is operator-controlled.
No synthetic tenant dashboard bindings are granted to protected Home.

TLS uses a tenant-local self-signed issuer. Import/verify its public certificate
on clients before sending credentials; do not disable TLS verification routinely.
There is no public DNS, public ACME, LoadBalancer, NodePort, host networking, or
router forwarding change. The hostname alone does not restrict access: only use
an approved LAN route with no WAN forwarding. The VM NAT addresses are not
assumed reachable from other LAN devices.

Redis, Collabora, preview workers, metrics exporter, SSO and database replicas
are deferred. APCu remains the local cache, PostgreSQL handles default file
locking, and the deployment has one web replica. Assess Redis before increasing
concurrency or scale. PostgreSQL 17 follows the platform's existing pin; confirm
support for the pinned Nextcloud release before deployment and never perform
unreviewed major database or application upgrades.

Storage is explicitly local-path, WaitForFirstConsumer, Delete reclaim policy.
The PVC retains data through application pod deletion and recreation on the
same healthy worker; this remains unverified until the acceptance exercise.
It cannot move data to another node. Worker failure leaves the application
unavailable; worker disk loss or lab rebuild loses both files and database.
The storage quota limits requested capacity, not necessarily bytes written to
local directories: this provisioner is not a hard disk usage limiter. Watch
actual node free space and do not claim enforced per-volume size limits.
