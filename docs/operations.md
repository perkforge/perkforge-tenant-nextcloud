# Operations

Read [HANDOFF.md](../HANDOFF.md) for current state and approval boundaries, and
[recovery.md](recovery.md) before data changes. The initial deployment and user
login are working. Procedures below describe future operation; they are not
pending steps for the current deployment unless marked unverified.

## Current access and ownership

Use `https://nextcloud.local-lab.test` and username `home-admin`, not `admin`.
The password is the contents of the platform checkout's ignored owner-only file
`.secrets/nextcloud/nextcloud-admin-password`. Do not print it into logs or copy it
into Git. The database password is a separate credential, not an app login.
Immutable Kubernetes Secrets reference both bootstrap credentials; never rotate
or recreate them accidentally during a retry.

The workstation last resolved the hostname to `192.168.122.201`. Authenticated
WebDAV checks succeeded through both `.201` and `.202`. The user confirmed
interactive access. The assistant did not change OS hostname or routing settings.
The workstation's LAN address was `192.168.1.183/24`; VMs use libvirt NAT subnet
`192.168.122.0/24`. Access from an independently verified second LAN device is
still unverified. DNS alone does not create that route. Any new route, bridge,
firewall rule or port forwarding requires separate approval and must retain
LAN-only access. No public exposure is configured.

TLS uses the tenant's self-signed issuer. Verify/import the public certificate
for normal clients; the exported public copy is in platform
`.secrets/nextcloud/public-tls.crt`. Re-export it after certificate rotation.
HTTPS/WebDAV acceptance verified the certificate. Browser automation used a
local-only TLS bypass in an ephemeral context, not installed client trust.

Platform Fleet registration is active, commit-pinned and lives in the dedicated
`fleet-home-nextcloud` workspace, mapped only to the existing fleet-local/local
cluster. The workload namespace belongs to Rancher Project local:p-home-local.
The platform owns foundation, namespace security, quotas, RBAC and registration.
This repo supplies the two explicit application bundle paths, database then app.
Use Fleet for declarative deployment; do not install/upgrade the same releases
manually with Helm. Private Secret bootstrap is the documented approved exception.

## New environment or reviewed upgrade

1. Inspect the platform's current handoff, target, storage, controllers and memory.
   For a new environment, start the application registration paused and provision
   the platform foundation/support before application resources.
2. Confirm the private hostname, route and certificate trust. Do not assume a
   Rancher-only issuer works in the application namespace.
3. With approval, use the platform helper
   `python3 local-lab/scripts/bootstrap-nextcloud-secrets.py --apply` after the
   protected namespace exists. Without `--apply` it prints a plan only. It must
   retain existing credentials; a missing local record for an existing Secret
   requires explicit recovery, not a new random password.
4. Run `python3 scripts/preflight.py` for a fresh deployment. Python3 and PyYAML
   are required. Current limits total 960 MiB (512 app + 320 DB + 128 cron);
   the gate adds 512 MiB reserve, requiring 1472 MiB worker headroom and 512 MiB
   control headroom. It also requires 8 GiB free on the worker filesystem backing
   local-path. The provisioner path was verified on worker root. This is an
   additional-workload startup gate, not a post-deployment health check or OOM
   guarantee. During upgrades account for the running workload separately.
5. Review image/chart/database compatibility and the paired recovery plan.
   PostgreSQL major upgrades require a separate migration. For protected data,
   verify a backup before upgrades or lifecycle changes.
6. Render the pinned Helm chart and check server admission. The current app and
   CNPG manifests passed these checks. Commit/push only with authorization.
   Update the application SHA in the platform registration. Remove `spec.branch`
   when pinning `spec.revision`; omit false-valued `paused` and `deleteNamespace`
   fields to avoid the normalization drift observed with this Fleet version.
   For a new registration, unpause only after support, Secrets and preflight.

The installed CNPG webhook requires `primaryUpdateStrategy: unsupervised` for
one instance. Upgrade approval comes from the operator-owned reviewed Git pin,
not supervised CNPG failover. Documentation-only application commits need not
advance the deployed workload pin.

Do not run the full platform deployment/rebuild scripts on this paused-Keycloak
profile: their identity checks assume Keycloak is running. Do not restart
Keycloak or enable observability without a new memory review. A VM rebuild also
destroys protected Nextcloud state; do not treat it as an ordinary synthetic tenant.

## Runtime configuration and troubleshooting

Nextcloud, its init container and CronJob use UID/GID33 and restricted security
contexts. No app service-account token is mounted. Persistent subdirectories
must be owned by UID33 with mode 0770; the init container creates them before
subPath mounts and fails closed on unexpected ownership. On the first rollout,
kubelet had already created root-owned 0777 directories; a scoped operator repair
changed only those directories on the new app PVC. No file contents were deleted.
Do not disable directory checks, format storage or add a privileged app container.

The trusted hostname is explicit in the mounted config. The startup hook sets
Cron mode idempotently. CronJobs run every five minutes with concurrency Forbid
and a 900-second deadline; Nextcloud 35 can process a batch for up to 14 minutes.
The one-worker Apache profile uses PHP memory_limit=192M and opcode cache 64 MiB,
within an app limit 512 MiB. KeepAlive Off is necessary here: idle backend
connections previously held the only worker for five seconds each, starving
parallel browser assets and probes. This is a low-concurrency trial profile.

If login fails, first confirm URL and `home-admin` username, current resolution,
certificate and app readiness. Do not reset a known-working account blindly.
The credentials were reverified through both ingress IPs, and the user confirmed
login. Check recent events/logs without exporting config.php or Secret values.
Initial pre-fix CronJob failures remain as history; later scheduled jobs completed.
Preserve evidence and do not reset data merely to clear historical errors.

## Acceptance and evidence

Observed acceptance passed:

- Nextcloud1/1, CNPG healthy 1/1, both PVCs Bound, certificate Ready, application
  Fleet 2/2, platform foundation 5/5 and existing platform-apps 4/4 Ready.
- Certificate-verified HTTPS/WebDAV upload/download and matching checksum after
  deleting/recreating only the application pod, with unchanged app/DB PVC and
  volume identities. The generated synthetic file was removed afterward.
- Browser login to `/apps/dashboard/` in a fresh ephemeral context, followed by
  user-confirmed interactive access. No browser state, screenshots or traces saved.
- Scheduled CronJobs completed, app runs as UID33 without an API token, selected
  Alpha-admin/Bravo-viewer access to Home denied, and deployer namespace/security/
  PVC-deletion permissions denied.

Successful private reports are in ignored `.evidence/smoke-20261027T011531Z/` and
`.evidence/browser-20261027T012251Z/`. Failed diagnostic attempts are retained.
A rendered policy and limited authorization checks do not prove all isolation.

To repeat persistence acceptance, obtain approval for the brief interruption,
upload only a generated synthetic file, record its checksum and app pod/PVC IDs,
restart only the app pod, wait for readiness, then download and compare the file
and PVC/volume IDs. Remove only that generated file. Never delete a PVC to test
persistence. A short quota retry was observed while the old pod terminated and
cron ran; the replacement recovered without increasing quotas.

Still unverified: separate LAN-client routing, database-pod restart, broader pod
network-denial paths, node-failure recovery, backup/restore and multi-user load.
Backup/restore is the next priority. Use replaceable data until it passes.

## Protected resource safeguards

GitRepo keepResources and namespace-deletion defaults, PVC/CNPG Helm keep
annotations, and the deployer's lack of direct PVC/Cluster deletion reduce
accidental removal risk. They do not cover cluster-admin actions, VM rebuilds,
all controller-mediated deletion, or node/disk loss. Offboarding, uninstall,
reset, destructive decommission and restore over existing data need their own
explicit authorization and recovery review.
