# PerkForge protected Nextcloud tenant

Application configuration for tenant `home`, namespace `tenant-home-nextcloud`,
environment `local-vm`. The platform repository provisions its Rancher Project,
namespace, restricted Pod Security, budgets, network policies, deployment RBAC,
and Fleet registration. This repository does not create those resources.

Status: prepared and locally rendered; not deployed or persistence-verified.
LAN routing and development secret bootstrap await operator decisions.

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
