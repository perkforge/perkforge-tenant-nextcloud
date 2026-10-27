# Operations

## Activation gates

1. Approve the development-only secret bootstrap. Run the platform helper only
   after the catalog namespace and support bundle are reconciled. It stores
   passwords in the platform's ignored .secrets directory and creates only the
   two referenced application Secrets. It must not rotate existing credentials.
2. Confirm `nextcloud.local-lab.test` and an existing private LAN route to the
   VM ingress. DNS/hosts entries must resolve to that reachable private address.
   No router, workstation firewall, bridging, or disk changes are implicit.
3. Measure fresh node memory and worker free disk. The proposed concurrent
   container memory limits total 1088 MiB (640 app + 320 database + 128 cron).
   Require at least 1600 MiB worker headroom and 512 MiB control headroom before
   starting, then watch startup and upload working sets. This budget is an
   operator gate, not a guarantee against OOM or off-container overhead. Do not
   increase VM RAM or restart Keycloak concurrently without a capacity review.
   Require at least 8 GiB free on the worker filesystem backing local-path;
   verify the actual provisioner path and filesystem rather than assuming root.
4. Review and publish this app repository and platform changes with explicit
   commit/push authorization. The platform registration is initially paused.
   Replace its branch with the reviewed full application commit SHA in
   `spec.revision`, remove `spec.branch`, and set `paused: false` in Git.
   Publish platform support before activating the registration. Register only
   the observed fleet-local/local cluster and target namespace.
5. Confirm existing CNPG operator and cert-manager are healthy. Render the chart
   with Helm 3, validate resources against the cluster with server dry-run,
   and check restricted Pod Security compatibility. These checks are pending.
   The chart was rendered locally; no Helm install/upgrade bypass is intended.

The paused registration intentionally prevents deployment until these decisions
are complete. All declarative deployment resources go through Fleet. Secrets
are the documented out-of-Git bootstrap exception, requiring approval.

## Acceptance

Observe Fleet bundle status, app rollout, CNPG readiness, PVC binding, certificate
readiness, events, probes, memory and disk use. Open the HTTPS LAN URL from a
separate LAN client and authenticate using the private admin credential file.
Set Nextcloud background jobs to Cron using `php occ background:cron` as UID 33;
verify scheduled jobs succeed. Do not claim this action has already run.

Upload a synthetic file via WebDAV, save its checksum, obtain the app pod UID,
then restart only the application Deployment with explicit approval for the
brief interruption. Confirm a new pod UID, unchanged PVC UID and Bound volume,
successful login and the same downloaded checksum. Also confirm a database pod
restart preserves state, as a separate approved interruption. Never delete a
PVC to test persistence. Capture sanitized results in ignored .evidence/.

Check synthetic tenant access is denied, the deployer cannot mutate policies or
delete data objects, app token mount is absent, cross-tenant pod traffic is
denied, and only intended ingress/database/DNS paths work. Platform namespace
labels and a rendered NetworkPolicy are configuration, not proof of enforcement.
No live application, restart, upload, policy, or browser acceptance has run yet.

## Protected changes

App GitRepo pins reviewed commits; keepResources and deleteNamespace:false
reduce uninstall risk. PVC and CNPG Cluster use Helm keep annotations. RBAC
withholds direct PVC/Cluster deletion from the deployer. These safeguards do not
protect against cluster admins, a VM rebuild, or every controller-mediated data
loss. Obtain a verified backup before upgrades or lifecycle changes.

Do not run the current full platform deployment/rebuild scripts while Keycloak
is paused: their identity checks assume it is running. Resume Keycloak through
GitOps only after reviewing worker capacity alongside Nextcloud. Do not perform
offboarding or destructive decommission for Home without explicit approval.
