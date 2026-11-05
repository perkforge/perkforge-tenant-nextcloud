# Physical Nextcloud tenant: draft, not activated

The supported proposal is `gitops/clusters/local`, composed from `gitops/base`.
Both HelmReleases are suspended. No current platform or enrollment root selects
this repository. The old `bundles/` inputs and VM operations evidence are
historical; they are preserved unchanged, not a second supported deployment path.
This proposal deploys a fresh empty instance, not a migration or an import.
Corey will guide household data housecleaning after deployment; do not mount,
scan, copy, reorganize or import household files as part of activation.

## Ownership and enrollment prerequisite

The active pattern is platform -> perkforge-platform-tenants -> app Git. The
portal enrollment provides the reference for separate config, runtime and Helm
storage namespaces and scoped reconciliation/deployment identities. Its exact
allowlists are portal-specific: do not reuse them unchanged or widen them to
wildcards. This app PR deliberately cannot grant its own isolation or authority.
A separate reviewed enrollment change is REQUIRED before activation:

| Platform/enrollment-owned item | Required contract |
|---|---|
| Namespaces | `tenant-home-nextcloud-config`, `tenant-home-nextcloud`, `tenant-home-nextcloud-release`; restricted Pod Security; no Pods in config/release namespaces |
| Git source | `tenant-nextcloud` in config namespace, published immutable reviewed app revision; initially suspended; never follow an unreviewed branch |
| Chart source | `nextcloud-upstream` HelmRepository in config namespace, URL `https://nextcloud.github.io/helm/`; operator-owned; only chart `nextcloud` version `9.4.1` allowed |
| App reconciler | ConfigMap and HelmRelease reconciliation in config namespace only; no namespace, RBAC or policy writes |
| Helm deployer | `nextcloud-deployer` in config namespace; namespaced workload/config/PVC/CNPG permissions in runtime, release Secret storage only in release namespace; no cluster-admin or security-foundation edits |
| Runtime identity | Default runtime ServiceAccount with `automountServiceAccountToken: false`; no app RBAC; CNPG instance-manager identity/RBAC reviewed separately |
| Admission | Pin release names, source/chart refs, target/storage namespaces, service account and values inputs; deny remote kubeConfig, authority bypasses, alternate sources and unsafe workloads |
| Network | Default deny ingress/egress; reviewed ingress-controller selector -> app TCP80; app/cron -> this DB TCP5432; DNS UDP/TCP53; CNPG operator -> instance manager TCP8000; database instance manager -> observed API endpoints only; no general internet or cross-tenant access |
| Budget | Reviewed quota/LimitRange including 48Gi requested storage, 2 PVCs initially, web/DB/cron plus transient Jobs and rollout headroom; CNPG-generated objects need explicit allowlists |
| Credentials | Preexisting `nextcloud-admin` and `nextcloud-db-app` username/password Secrets in runtime namespace; immutable/persisted credentials via approved secret workflow; TLS `nextcloud-tls` with private LAN hostname SAN and trusted client chain |
| Controllers | Healthy Flux source/helm/kustomize controllers and reviewed CNPG operator/CRDs; no tenant installation of cluster-wide operators |

Do not claim a real isolated tenant until those foundations and live positive/
negative tests pass. No foundation manifests are hidden in the application chart.
CNPG needs instance-manager access to Kubernetes; denying all API access to every
Pod would break it. Grant only its observed requirements, not app token access.
No public ingress, router forwarding, SSO, Redis or external storage is enabled.

The data HelmRelease owns only the retained CNPG Cluster. The app release owns
the retained files PVC alongside its consuming Deployment, using the existingClaim
setting to share it with cron and preexisting Secrets. Helm storage is separate from runtime
credentials. `helm.sh/resource-policy: keep`, `prune: false` in the future
enrollment Kustomization, and denied direct PVC/Cluster deletion reduce accidental
loss; they do not prevent every controller-mediated deletion or admin action.
Review Helm uninstall/update admission and CNPG behavior before granting deployment
authority; namespace-only RBAC alone is insufficient isolation.

## Minimal local values and storage gate

`gitops/clusters/local` selects only the private hostname/ingress, prepared worker
label and proposed storage requests. It contains no disk paths, UUIDs, hostnames
or IP addresses. The shared values retain the tested restricted UID33 initialization,
serial Apache profile, Recreate/RWO strategy and non-overlapping five-minute cron.
This remains a low-concurrency starting profile, not accepted household capacity.

The existing platform main at inspection (`babaf4416c3e5929e4956c9986379976b88109fa`)
already defines `longhorn`, Retain, two replicas and prepared-worker selectors.
This draft uses that interface, not any unmerged SSD implementation. After SSD
relocation, explicitly verify the ACTUAL class provisioner, Retain reclaim,
binding behavior, replica health across workers, scheduling labels, capacity and
reserved/headroom budgets. The 32Gi files and 16Gi database requests are proposed
PVC budgets, not observations of disks or usable capacity. Replication, snapshot
space, existing workloads and rebuild headroom consume additional capacity.
No default StorageClass fallback, local-path fallback, formatting, relocation or
storage migration is supplied by this PR. The reusable data chart refuses to
render without an explicit reviewed class selection.

The files PVC belongs to the app release: placing a WaitForFirstConsumer PVC in
an earlier release with normal Helm waits creates a cycle (data waits for claim
binding, app waits for data, binding waits for app). Keep install/upgrade waits
enabled; the database-only release has its own CNPG-managed consumer. See
[Kubernetes binding semantics](https://kubernetes.io/docs/concepts/storage/storage-classes/#volume-binding-mode)
and [Flux Helm waits/dependencies](https://fluxcd.io/flux/components/helm/helmreleases/).

Cron has required Pod affinity to this release's app component on
`kubernetes.io/hostname`, scoped to its own namespace by Kubernetes defaults.
Its shared worker selector alone cannot co-locate RWO users. Without a web pod,
cron waits rather than attaching the volume on another worker. Affinity is
ignored during execution: drain/recovery must quiesce existing cron writers before
moving the web workload, then verify detach/reattach. Do not claim live failover
from an offline render. The selector deliberately excludes cron itself.

Longhorn replicas/snapshots are not an independent backup. A single Nextcloud pod
and single PostgreSQL instance do not provide application/database HA; test RWO
reattachment and recovery separately after storage acceptance.

## Ordered future activation (separately approved)

1. Review/merge/release storage work and complete SSD move/storage acceptance first.
   Resolve app/chart/PG17.6 compatibility and image security/digest pins. Existing
   historical image tags are retained to avoid silently upgrading a database.
2. Publish this app only after review; prepare/review the enrollment foundation
   and tag/SHA pin separately. Start source, enrollment and both releases paused.
3. Deliver existing approved credentials and private TLS trust without printing
   them, and validate quota, controllers and network/authorization boundaries.
   The Nextcloud DB connection currently retains historical chart defaults;
   review encrypted database transport and CA/hostname validation before activation.
4. Recheck the rendered data resources and budget; unpause only the data release
   under separate live approval. Verify CNPG Cluster Ready, its database claim
   Bound, bootstrap credentials and actual database-volume replication. The files
   PVC is created later with the app; do not require it Bound before app activation.
   A HelmRelease Ready alone
   does not establish readiness of a custom CNPG resource. Keep app paused until
   these checks pass. On failure preserve resources and diagnose; no reset.
5. Unpause app only after the database gate. The app release creates its retained
   files PVC and web Deployment together, allowing WaitForFirstConsumer binding.
   Verify files PVC Bound and healthy replication before accepting app readiness.
   Verify private certificate-trusted HTTPS,
   login, scheduled cron, synthetic WebDAV checksum retention over app restart,
   and denied tenant-to-tenant network/authorization paths. Confirm no app token.
6. Complete paired backup and isolated restore below before real data. Record
   actual capacity/load observations and recovery timings. Household import is a
   later Corey-guided task, not authorized by merge or deployment acceptance.

No merge, publication, offline build or successful CI authorizes these live steps.

## Backup and restore readiness

No backup destination or successful restore is configured or claimed. Before
activation choose an encrypted destination outside this cluster and its SSDs,
access/credential custody, schedule, retention, capacity and intended RPO/RTO.
The existing GitLab Garage is not assumed available or an approved independent
backup destination. Automated backup jobs/credentials are deferred until those
choices are reviewed; there is no fake success or backup-ready flag.

For the first synthetic-data exercise, use a reviewed GitOps maintenance window:
enter Nextcloud maintenance mode, suspend cron and stop ALL app writers, confirm
quiescence, then export a consistent matching PG17 logical dump AND the entire
files PVC (root/html/config/data/custom_apps/themes/tmp as applicable). Preserve
instance secrets/encryption keys, credential custody, UID/GID33 permissions,
checksums, exact app/chart/database/source versions, timestamps and manifest
metadata with the encrypted backup. Secrets, config.php, dumps and user files
must remain outside Git. Resume writers only after both backups verify.

Restore into a separately approved isolated namespace with matching versions,
no normal ingress, no cron and no household access. Restore the paired database
and files/config snapshot with original instance keys/ownership. Verify login,
DB consistency, synthetic file checksums and background jobs before considering
cutover. Record measured RPO/RTO and a failure/retry procedure. Never overwrite
existing claims or roll an older image over an upgraded schema. A future
migration needs separate source inventory, clean-up direction from Corey, backup
and action-specific approval; this PR does not touch the historical VM instance.

## Offline checks

Requires Python3/PyYAML, kubectl and Helm. Fetch the official chart archive from
its index, verify SHA256
`e3d768864800bcc23eb66e6f65cbf5f0545b1506cf8c65f55a91d21af3bad4bf`, then:

```sh
kubectl kustomize gitops/clusters/local > /tmp/nextcloud-flux.yaml
NEXTCLOUD_CHART=/path/to/verified/nextcloud-9.4.1.tgz python3 -m unittest discover -s tests -v
```

`HELM` may point to the Helm executable. Tests build the actual local selection
and render the pinned upstream chart plus data chart, checking suspension/scoped
namespaces, worker scheduling, claim sharing, UID33, cron concurrency, private TLS
reference, retained data and rejection of an unselected storage class. They do
not contact Kubernetes or prove controller admission, isolation, storage capacity,
upstream image availability, database TLS or backup/recovery success.
