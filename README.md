# PerkForge protected Nextcloud tenant

Application configuration for tenant `home`, namespace `tenant-home-nextcloud`,
environment `local-vm`. The platform repository provisions its Rancher Project,
namespace, restricted Pod Security, budgets, network policies, deployment RBAC,
and Fleet registration. This repository does not create those resources.

Status: deployed through Fleet on 2026-10-26. Application and database are
Ready; certificate-verified HTTPS/WebDAV upload/download and checksum retention
across an application-pod restart passed. Browser login reached the dashboard
using a local-only self-signed TLS bypass. The application is a low-concurrency
VM trial; external LAN-client routing and backup/restore remain unverified.

Open `https://nextcloud.local-lab.test` after mapping that hostname to
`192.168.122.202` on a client that can route to the VM subnet. The admin username
is `home-admin`; its password is in the platform checkout's ignored private file
`.secrets/nextcloud/nextcloud-admin-password`. No password is stored here.
The public self-signed certificate is exported privately on the workstation at
`.secrets/nextcloud/public-tls.crt`; verify/import it for normal browser trust.
Host/router networking and workstation hostname resolution were not changed.

Fleet must scan exactly `bundles/database` and `bundles/nextcloud`. There is no
root bundle. The first creates one PostgreSQL cluster using the existing CNPG
operator; the second installs the community Nextcloud chart and waits for that
bundle. TLS resources are included via chart `extraManifests`.

| Component | Pin | Storage |
|---|---|---|
| Nextcloud Helm chart | 9.4.1 | — |
| Nextcloud Apache image | docker.io/library/nextcloud:35.0.2-apache | 4 GiB local-path RWO |
| PostgreSQL | ghcr.io/cloudnative-pg/postgresql:17.6 | 2 GiB local-path RWO |

The chart archive SHA256 was checked against its repository index:
`e3d768864800bcc23eb66e6f65cbf5f0545b1506cf8c65f55a91d21af3bad4bf`.
Pins are reproducible version tags, not immutable image digest locks. Verify
registry availability and database compatibility before activation.

Use [operations](docs/operations.md), [architecture](docs/architecture.md), and
[recovery](docs/recovery.md). Do not load irreplaceable files into this VM proof
of concept. Protected status requires reviewed changes and backups; it does not
make local-path storage highly available or protect against cluster admins.

Upstream references: [chart](https://nextcloud.github.io/helm/),
[chart source](https://github.com/nextcloud/helm/tree/nextcloud-9.4.1/charts/nextcloud),
[Nextcloud system requirements](https://docs.nextcloud.com/server/latest/admin_manual/installation/system_requirements.html).

Observed runtime fixes are encoded in values: UID33 initializes PVC subdirectories
before subPath mounts, the hostname is explicitly trusted, a startup hook sets
Cron mode, and Apache KeepAlive is disabled so one request worker does not
starve browser assets or probes. The first rollout required a one-time scoped
ownership repair on newly created root-owned subdirectories; no data was reset.

Successful private evidence is under `.evidence/smoke-20261027T011531Z/` and
`.evidence/browser-20261027T012251Z/`. Earlier failed startup/browser attempts are
retained as private diagnostics. Broad network isolation, backup restore,
node-failure recovery and multi-user load are not acceptance claims.
