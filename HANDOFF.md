# Nextcloud operator handoff

Last updated: 2026-10-26 (America/Chicago; evidence timestamps use UTC).

## Current state

The initial working trial is complete. The user confirmed interactive access and
login after the deployment. Nextcloud and its PostgreSQL database are Ready;
Fleet reports both application bundles Ready. This is a protected tenant on a
disposable VM cluster, with persistent local volumes and no verified backup.

| Item | Current value |
|---|---|
| App checkout | `/home/corey/src/perkforge-tenant-nextcloud` |
| Platform checkout | `/home/corey/src/perkforge-platform` |
| Tenant / environment | `home` / `local-vm` |
| Namespace | `tenant-home-nextcloud` |
| Rancher Project | `local:p-home-local` |
| Fleet GitRepo | `fleet-home-nextcloud/tenant-home-nextcloud` |
| Fleet target | Existing `fleet-local/local` cluster |
| Deployed application revision | `3feb9b09686d5e1e08e9bf6616f6126335a1653f` |
| Helm / app / database | Nextcloud chart `9.4.1`, image `35.0.2-apache`, PostgreSQL `17.6` |
| URL / username | `https://nextcloud.local-lab.test` / `home-admin` |
| Last observed workstation resolution | `192.168.122.201` |
| Workload placement | `cks-worker` (`192.168.122.202`) |

Both `.201` and `.202` ingress addresses accepted authenticated WebDAV requests
using the same credentials and verified public certificate. Automated browser
login reached `/apps/dashboard/`; the user subsequently confirmed access.
Do not assume the user's device proves routing from all home-LAN clients.
The assistant did not change hosts files, router routes, firewall or bridging.
No hostname change is currently needed for the user's working access.

Later commits on application `main` update documentation only; the platform
intentionally pins the tested workload revision rather than following `main`.
Do not advance the deployment pin just to publish documentation.

## Ownership and protected changes

Read `AGENTS.md`, `docs/operations.md`, `docs/recovery.md`, and the platform's
`AGENTS.md` and `HANDOFF.md` before operational changes.

The platform owns the catalog, Rancher Project, namespace, quotas, LimitRange,
restricted Pod Security, policies, service-account boundaries and Fleet
registration. Its source files are:

- `local-lab/tenant-config/tenants.yaml`: small catalog index.
- `local-lab/tenant-config/tenants/home.yaml`: editable Home tenant record.
- `local-lab/fleet/bundles/tenant-foundation/tenants/home/`: generated foundation.
- `local-lab/fleet/bundles/nextcloud-support/`: deployment RBAC, policies,
  FleetWorkspace, Fleet Policy and BundleNamespaceMapping.
- `local-lab/fleet/bundles/nextcloud-registration/gitrepo.yaml`: workload SHA pin.

This repo owns only `bundles/database` and `bundles/nextcloud`; those are the two
explicit Fleet paths. There is no root or duplicate application bundle.
The dedicated Fleet workspace requires `home-nextcloud-deployer`, restricts the
repository and disables namespace creation. The deployer cannot patch workload
namespace metadata, change policies/quotas/RBAC, or delete PVCs/CNPG Clusters.
It still has significant tenant-local deployment and Secret authority.

GitRepo keepResources, Helm keep annotations and scoped RBAC reduce accidental
removal risk; they do not protect against all controller actions, node loss or
cluster admins. Never delete data resources, uninstall, reset or rebuild without
explicit action-specific authorization and the applicable recovery decision.
The completed deployment authorization is not blanket approval for future wipes.

## Credentials and TLS

Only the platform's ignored, owner-only files contain bootstrap passwords:
`.secrets/nextcloud/nextcloud-admin-password` and
`.secrets/nextcloud/nextcloud-db-app-password`. Never print or commit their contents.
Two immutable Kubernetes Secrets reference those credentials. Do not rerun a
bootstrap with new values, reset the account, or assume the DB password is an
application password. Application username is `home-admin`, not `admin`.

TLS is tenant-local and self-signed. The public certificate was exported to the
platform `.secrets/nextcloud/public-tls.crt`; re-export the public certificate if
it rotates. HTTPS/WebDAV checks verified that certificate. Automated browser
checks used an ephemeral context with a local-only TLS bypass, not persistent
client trust. Verify/import the public certificate for regular client use.

## Storage, capacity and runtime fixes

The worker virtual disk is now 100 GiB, root XFS about 95 GiB; the platform
provisioning script creates future workers with the same size and root layout.
Control remains 30 GiB. No physical drive was repartitioned or formatted.

PVCs `nextcloud-nextcloud` (4 GiB) and `nextcloud-db-1` (2 GiB) use explicit
`local-path`, RWO, WaitForFirstConsumer, Delete reclaim. They remain tied to the
worker disk; there is no HA, replication, automatic failover or verified restore.
Requested storage quotas are not hard limits on local directory bytes.

Current memory limits are app 512 MiB, DB 320 MiB and cron 128 MiB. PHP uses
192M with a 64-MiB opcode cache; Apache has one worker and KeepAlive Off to avoid
idle connections starving browser assets and probes. The profile is for a
small trial, not validated multi-user load. The init container runs as UID33,
creates persistent subdirectories and checks their ownership/mode. First rollout
required a scoped ownership repair of root-owned 0777 directories on this PVC;
no file contents were deleted or reset. Do not disable permission checks or
introduce privileged app containers as a workaround.

The trusted hostname is explicit in config. A startup hook sets Cron mode.
CronJobs run every five minutes with concurrency Forbid and a 900-second deadline.
The installed CNPG operator requires unsupervised updates for a single instance;
reviewed Git pins control upgrades. The preflight script is a fresh-deployment
capacity gate, not a post-deployment health check that accounts for existing use.

Keycloak remains paused at zero application replicas; its database is retained.
Do not restart it or enable observability without reviewing memory headroom.
The full platform deploy/rebuild scripts still assume running Keycloak; do not
use them to verify this paused-identity profile or recreate protected data.

## Verification and evidence

Passed: application/database readiness, certificate-verified HTTPS/WebDAV
upload/download, matching checksum after an application-only pod restart,
unchanged app/database PVC and volume identities, browser login, successful
scheduled CronJobs, UID33 with no API token mounted, selected Alpha/Bravo
namespace authorization denials and deployer permission denials.

Private evidence remains in this repo's ignored `.evidence/`, notably
`smoke-20261027T011531Z/summary.json` and
`browser-20261027T012251Z/summary.json`. Failed initial attempts are retained.
The initial failed CronJob is historical; later runs completed. Do not delete
evidence or reset workloads merely to hide that history. No credentials, browser
state, screenshots, or traces were committed. Temporary verification drivers
under `/tmp` are not durable dependencies; operations.md describes the exercise.

## Safe resume and next work

Start with read-only checks:

```sh
kubectl get nodes
kubectl get gitrepos -A
kubectl get deployments,clusters.postgresql.cnpg.io,pvc,certificates,jobs -n tenant-home-nextcloud
kubectl get statefulset -n keycloak
```

Expected: app 1/1, CNPG healthy 1/1, both PVCs Bound, certificate Ready, app Fleet
2/2, platform foundation 5/5, platform-apps 4/4, Keycloak 0/0. Counts describe
this profile and may change after a reviewed future change.

Next priority is a paired database/application-volume backup to an approved
location outside both VM disks and a verified isolated restore. Use replaceable
data until that succeeds. Then broaden network-denial and separate LAN-client
checks. Database-pod restart, node-failure recovery, full lifecycle/offboarding,
SSO, hard storage enforcement and multi-user load remain unverified. Keep SSO,
Redis, observability, public exposure and destructive lifecycle work out of scope
unless separately requested. Any future upgrade needs compatibility review and
a verified backup; never roll an old image back over a migrated schema.
