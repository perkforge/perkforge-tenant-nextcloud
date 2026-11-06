# Physical Nextcloud tenant: draft, not activated

The supported proposal is `gitops/clusters/local`, composed from `gitops/base`.
Published v1.0.1 enables only the database HelmRelease. This later candidate
enables web after database acceptance; cron remains suspended. No current platform or enrollment root selects
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

## Owner administration and tenant isolation

Corey remains the platform owner/administrator while Nextcloud runs as an isolated
tenant. This app does not change cluster-admin, Keycloak platform roles, Rancher,
API authentication or existing administrator bindings. Platform authority includes
managing the tenant foundation and recovery; scoped tenant automation does not
receive that authority. Namespace admission also constrains routine operator
workloads inside the tenant, but the platform owner retains authority to review
and change those operator-owned boundaries. Tenant isolation is not a restriction
on who owns the home cluster.

| Identity | Authority |
|---|---|
| Corey's platform-admin identity/recovery kubeconfig | Platform and tenant lifecycle, policy, storage, credentials and recovery |
| nextcloud-reconciler / nextcloud-deployer | Only the named app resources under the reviewed tenant boundary |
| Nextcloud web/cron default ServiceAccount | No Kubernetes API token or application RBAC |
| Corey's Nextcloud application-admin account | Nextcloud users, settings and app administration; no implied cluster access |

For the fresh instance, the operator delivers `nextcloud-admin` username/password
Secret keys; chart env NEXTCLOUD_ADMIN_USER/PASSWORD feed the official image's
`occ maintenance:install --admin-user/--admin-pass` path. This creates the initial
Nextcloud administrator independently of Kubernetes/Keycloak membership. Choose
Corey's intended local admin username through protected inputs, then verify its
actual Nextcloud `admin` group and administrator UI after initialization. No
username/password is guessed or copied from the historical VM. Keep tested local
admin recovery available; changing the bootstrap Secret is not an existing-user
password-reset mechanism.

SSO is intentionally absent from this pilot. A later reviewed integration must
select/pin its supported Nextcloud OIDC/SAML app, create the scoped Keycloak client,
and explicitly configure and test subject/group/admin mapping. Existing
`/platform/admins` access to Kubernetes/Rancher does **not** automatically grant
Nextcloud application admin. Test Corey's intended admin mapping and an ordinary
household user's non-admin access separately before relying on SSO. Retain local
recovery access through that change; no global identity or admin grants are changed
by deploying an isolated tenant.

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
label, logical node preference and pilot storage requests. It contains no disk
paths, UUIDs or physical IP addresses. The shared values retain restricted UID33 initialization,
serial Apache profile, Recreate/RWO strategy and non-overlapping five-minute cron.
This remains a low-concurrency starting profile, not accepted household capacity.

The local selection requires `longhorn-dedicated`, accepted on the physical cluster
at platform v0.19.0 (`31128eff057217a7da740cd82c7c26547f6fdb62`). The guarded
UUID-based XFS mounts and enabled SSDs passed a dedicated 1Gi write/checksum,
same-worker recreation and cross-worker reattachment test with two actual SSD
replicas and RW engine modes. Original volume placement was preserved. This is
storage acceptance, not Nextcloud or backup/restore acceptance. Both files and
database use that exact class; generic `longhorn` cannot guarantee SSD placement.
Recheck current health, free space and the live contract before allocation. The class
must be nondefault `driver.longhorn.io`, Retain, WaitForFirstConsumer, two V1
replicas, hard node/disk anti-affinity and `diskSelector: dedicated-storage`.

After SSD relocation verify ACTUAL dedicated disks, stable persistent mounts,
missing-drive/boot behavior, exact disk tags, enabled scheduling, class parameters,
replica health across workers, scheduling labels, measured capacity and reserved/
headroom budgets. Class existence alone is insufficient. With allocation approved,
verify BOTH newly created file/database volumes' replicas actually reside on the
accepted dedicated SSD disks; do not accept class-name matching as placement proof.
The 32Gi files and 16Gi database requests are proposed PVC budgets, not observations
of disks or usable capacity. Replication, snapshot space, existing workloads and
rebuild headroom consume additional capacity. Keep both HelmReleases suspended
and STOP before allocation if the reviewed tier is missing or unaccepted. Do not
substitute generic `longhorn` or relabel existing root disks to make it pass.
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
Its shared worker selector alone cannot co-locate RWO users. Affinity matches
Pod placement, not Pod readiness or completed init containers. Therefore the
CronJob starts with `cronjob.cronjob.suspend: true`. On a fresh volume a concurrent
cron mount could create missing subPaths through kubelet before the web UID33
initializer, leaving unexpected owners and failing its strict checks. The pinned
chart gives cron no directory-preparation init container. Keep cron suspended
until web directory preparation AND Nextcloud instance initialization succeed.
See [kubelet subPath creation](https://github.com/kubernetes/kubernetes/blob/v1.36.0/pkg/kubelet/kubelet_pods.go)
and [CronJob suspension](https://kubernetes.io/docs/concepts/workloads/controllers/cron-jobs/#schedule-suspension). Without a web pod,
cron waits rather than attaching the volume on another worker. Affinity is
ignored during execution: drain/recovery must quiesce existing cron writers before
moving the web workload, then verify detach/reattach. Do not claim live failover
from an offline render. The selector deliberately excludes cron itself.

Longhorn replicas/snapshots are not an independent backup. A single Nextcloud pod
and single PostgreSQL instance do not provide application/database HA; test RWO
reattachment and recovery separately after storage acceptance.

## Ordered future activation (separately approved)

1. Recheck accepted platform v0.19.0 storage health and actual disk placement;
   never substitute the generic class.
   Storage acceptance is recorded above. The official chart 9.4.1 archive matches
   its index SHA256 and declares appVersion 35.0.2. Both images were resolved from
   their public registries with Linux amd64 manifests and are pinned by immutable
   multi-architecture index digest. Review support/security before activation;
   availability and offline rendering do not prove runtime compatibility.
   The fresh database selects PostgreSQL 17.11 at the same digest observed healthy
   under the platform's current CNPG operator, rather than the old VM's 17.6 pin.
   This is an initial image selection, not an upgrade or mutation of an existing DB.
2. Publish this app only after review; prepare/review the enrollment foundation
   and tag/SHA pin separately. Start source, enrollment and both releases paused.
3. Deliver existing approved credentials and private TLS trust without printing
   them, and validate quota, controllers and network/authorization boundaries.
   Deliver only the CNPG public CA in runtime ConfigMap `nextcloud-db-ca`, never
   its signing key. Web/cron mount it read-only at `/etc/nextcloud-postgres-ca`.
   Native `pgsql_ssl` selects `verify-full`; PGSSLMODE/PGSSLROOTCERT protect initial
   installer connections too. CNPG rejects plaintext host connections before its
   default HBA rule. Verify the Service hostname SAN and CA fingerprint before app
   activation; never weaken hostname checking to make startup pass.
4. Recheck the rendered data resources and budget; unpause only the data release
   under separate live approval. Verify CNPG Cluster Ready, its database claim
   Bound, bootstrap credentials and actual database-volume replication. The files
   PVC is created later with the app; do not require it Bound before app activation.
   A HelmRelease Ready alone
   does not establish readiness of a custom CNPG resource. Keep app paused until
   these checks pass. On failure preserve resources and diagnose; no reset.
   The reviewed data-stage source enables only `nextcloud-data`; pin its published
   release through enrollment/platform before promotion. It creates no web Pod,
   files claim or cron Job. Do not manually unsuspend web against paused Git values.
5. Publish and select this web-stage candidate only after the database gate;
   do not manually resume it against the selected v1.0.1 values. The app release creates its retained
   files PVC and web Deployment together, allowing WaitForFirstConsumer binding.
   Verify files PVC Bound and healthy replication before accepting app readiness.
   Run the owner-operated read-only probe in the existing web container:

   ```sh
   kubectl -n tenant-home-nextcloud exec -i deployment/nextcloud -- php \
     < scripts/verify_database_tls.php
   ```

   It verifies a real TLS session and wrong-CA, wrong-hostname and plaintext denials
   for expected reasons, without database writes or credential output. Its temporary
   unrelated public CA is removed. This live probe has not run against an undeployed
   Nextcloud instance.
   Keep the rendered CronJob suspended while web UID33 directory preparation and
   Nextcloud installation complete. Verify web Ready, initialized instance,
   expected persistent-directory ownership and private certificate-trusted HTTPS
   login. Only then make a separately reviewed GitOps change in local app values
   setting `cronjob.cronjob.suspend: false`; do not unpause cron with the initial
   HelmRelease activation. Verify a scheduled job succeeds on the web node.
   Unsuspending may immediately start a missed run; approve only after the gate.
   Suspension does not stop already-running Jobs: maintenance/restore must also
   quiesce existing writers. Repeat this suspension/initialization sequence for
   any fresh claim or isolated restore. Then verify synthetic WebDAV retention,
   and denied tenant-to-tenant network/authorization paths. Confirm no app token.
6. Complete paired backup and isolated restore below before real data. Record
   actual capacity/load observations and recovery timings. Household import is a
   later Corey-guided task, not authorized by merge or deployment acceptance.

No merge, publication, offline build or successful CI authorizes these live steps.

The 32Gi files/16Gi database claims are an empty pilot. At review worker-1 had
280m CPU unreserved and worker-2 1420m; each has six CPUs and about 15.2GiB
allocatable memory. Web/database request 250m/576Mi combined plus 25m/64Mi during
cron. Local affinity prefers worker-2 while retaining worker-1 as eligible; cron
still requires the web node. Recheck CI/rollout headroom before activation. Low
instantaneous CPU usage is not reserved capacity. Keep the serial Apache/256M
upload profile initially and measure photo/video behavior before increasing it.
Expand before household import only after accounting for database, snapshots,
growth and any future existing-volume migration in the important-data budget.
Single-excess storage is not selected by this application.

Configuration references: [Nextcloud 35 connection factory](https://github.com/nextcloud/server/blob/stable35/lib/private/DB/ConnectionFactory.php),
[PostgreSQL TLS verification](https://www.postgresql.org/docs/17/libpq-ssl.html),
and [Nextcloud 35 requirements](https://github.com/nextcloud/documentation/blob/stable35/admin_manual/installation/system_requirements.rst).

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
namespaces, worker scheduling, claim sharing, UID33, initial cron suspension and
post-initialization cron rendering, cron concurrency, private TLS
reference, retained data and rejection of an unselected storage class. They do
not contact Kubernetes or prove controller admission, isolation, storage capacity,
upstream image availability, database TLS or backup/recovery success.
