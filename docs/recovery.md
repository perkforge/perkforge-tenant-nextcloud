# Backup and recovery

No backup destination, schedule, retention policy, or successful restore exists
for this tenant. The initial VM deployment is a proof of concept and must use
synthetic or replaceable files until a backup and restore exercise passes.

Before real data or any upgrade, select an operator-approved destination outside
both VM disks. No existing SSD may be formatted or repurposed. Configure a
consistent backup of PostgreSQL, Nextcloud's full persistent application volume
(including data, config, custom_apps, themes and instance secrets), and the
private bootstrap credentials. Encrypt exported material and restrict access.
Do not put dumps, config.php, credentials or user files into either Git repo.

For a manual cold backup, enter maintenance mode, stop all writers including the
CronJob and web workload through a reviewed GitOps change, then collect a
PostgreSQL logical dump with the matching PG17 tools and archive the application
volume through an approved job. Store checksums, exact image/chart/app commit,
CNPG manifest version, timestamp, and restore instructions with the encrypted
backup. Validate completion before re-enabling writers. A database dump alone
cannot restore Nextcloud files; a file archive alone cannot restore metadata.

Restore first into an isolated namespace with matching versions and fresh
platform-owned policies, no production ingress, and no scheduled writers.
Restore the database and matching application/config snapshot, preserving UID33
permissions and instance encryption keys. Use Nextcloud maintenance/repair and
schema verification as documented for that pinned version. Validate login,
file checksums, background jobs, and data consistency before switching ingress.
Record RPO/RTO from the exercise rather than claiming targets were met.

Application-pod restart was verified to retain an uploaded file and the same
PVC/volume identities on cks-worker. This is not a backup or restore exercise. Node outage: wait
for the same node/disk recovery. Lost worker disk: restore both data sets from an
external backup; a rescheduled pod does not recover local-path content.

Application upgrade: review chart/image/DB support together, take and verify the
paired backup, stop writers, and advance one supported Nextcloud major version
at a time. Do not roll an older image back over an upgraded database. Recovery
from a failed schema migration requires the matching pre-upgrade database AND
volume backup. PostgreSQL major upgrades require a separate migration plan;
changing the image tag alone is not an upgrade procedure.
