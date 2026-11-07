# Nextcloud SSO image candidate and gated lifecycle

The source values select the published image candidate described below; the live
enrollment remains pinned to v1.0.4. Every Ansible entrypoint defaults off and skips all commands, private inputs and API
contact in check mode. Future live runs require operation-specific approval,
verified local recovery and external operator inputs. Publication is separate
from activation; no merge or successful fixture authorizes a live stage.

## Artifact, image and values

Download the official built artifact in `artifact.yaml` on an approved workstation
connection. `prepare.yaml` with `nextcloud_sso_prepare=true`, an absolute
`nextcloud_sso_archive` and fresh `nextcloud_sso_output` verifies its published
SHA256 and assembles an offline Docker context. Existing/interrupted output is
preserved and refused. The Dockerfile repeats the hash check and retains signed
app files/dependencies under `/opt/perkforge/apps`, outside initialization and the
persistent custom_apps directory. It installs/enables nothing automatically.

The manual `sso-image-review` workflow builds with network disabled after pulling
the immutable base, inspects as UID33 and uploads a seven-day review image archive,
source commit, image metadata and archive hash. It has no package-write permission
and does not publish an image. Review archive provenance, scan/SBOM, supported
architecture and native integrity before a separately approved registry copy to
`ghcr.io/perkforge/nextcloud-sso:35.0.2-oidc8.13.0`. Obtain the actual registry
manifest digest after copying; a local image ID/archive hash is NOT that digest.
No fake digest, overwrite of existing tags or runtime download is supplied.

After publication, `nextcloud_sso_render_values=true` and `nextcloud_sso_image`
set to the exact tagged digest additionally render `candidate-app-values.yaml`.
That file preserves existing settings while changing only app/init/cron image and
adding exact read-only OIDC public-CA/client-secret mounts and the reviewed HTTPS
CLI origin. Supply `nextcloud_sso_origin` with image rendering. It is not selected.
Enrollment's unselected renderer produces matching exact-digest admission, and
its independent delivery stage consumes an EXISTING external client secret.

## Native operations

Use `ansible-playbook sso/reconcile.yaml -e @/absolute/private/operator.yaml`.
Each future run needs `nextcloud_native_run=true`, operation `X` and
`nextcloud_native_approval=nextcloud-native-X-v1`. Inputs identify explicit
kubeconfig/context, cluster UID, Pod name/UID, reviewed image digest and local
recovery username. The selected web container must be UID33 on Nextcloud 35.0.2;
no new exec RBAC is granted. Supply only externally held inputs, never Git secrets.

| Operation | Result and additional gate |
|---|---|
| inspect | Verify exact existing provider, issuer/client/scope/flags, system policy and local recovery; no mutation |
| prepare | Read retained provider inventory before mutation; refuse foreign/changed IDs. Copy only missing signed app from embedded artifact using a retained staging directory, check integrity/version, set strict policy and retain local backend, then enable app without creating a provider |
| apply | Verify mounted secret/CA byte hashes, import the public CA only if absent, configure separately approved private HTTP and create only a missing deny-all provider. Existing providers must match the supplied numeric ID; no updates/adoption/secret rotation |
| activate | Require reviewed `own-client-role-jit-v1` provisioning and client-ready evidence, verify trusted exact discovery/endpoints/S256/JWKS, then change only the login-role whitelist |
| grant-admin | Verify provider/hash identity, existing user_oidc backend and an actual direct owner grant on the canonical owned Keycloak client, then add only that OIDC user to native admin |
| remove-subject | Disable only the verified hashed OIDC user, remove its native admin membership, delete its Nextcloud authentication tokens and verify none remain; retries resume after interruption |
| resume-subject | Verify an actual direct household/owner client grant, require no native admin membership, then enable only that OIDC account. Admin grant remains separate |
| rollback | Return only the provider whitelist to deny-all, preserving its numeric identity and all data; require explicit evidence that affected native sessions were revoked first |

Apply additionally requires `nextcloud_private_http_approval=oidc-private-issuer-egress-v1`,
`nextcloud_ca_sha256` and `nextcloud_secret_sha256`. The secret hash is of the exact
mounted bytes (delivery trims the external file), not a newline-bearing source file.
Read and record the newly created numeric provider ID through the read-only
`occ user_oidc:providers --output=json` interface; supply it for every later run.
Never recreate a provider: numeric ID plus immutable subject defines the account.
Admin/resume operations require an external owner-only short-lived Keycloak
operator-token file, public CA and exact canonical client UUID. No token is minted.

The candidate chooses JIT user creation only for reviewed direct own-client role
holders, with `soft_auto_provision=false`, immutable sub and unique IDs. It does
not link by email/username or treat disabling auto provisioning as pre-provisioning.
Group provisioning and bearer login/provisioning are off; role names do not create
native admin. Initial owner login is non-admin until explicit native grant.

`allow_local_remote_servers=true` is necessary for the private issuer because the
upstream app supplies no per-issuer HTTP exception. This broadens Nextcloud's HTTP
address guard; it requires separately approved, tested narrow network egress.
Default network policy still denies it. Debug/self-signed bypass is refused.
Do not activate if the shared ingress /32 exposes unacceptable other destinations.

For removal/demotion: native remove-subject FIRST, then revoke/change only this
client's direct role using the platform adapter. Household resumption is a
separate verified operation. No realm-wide logout, user deletion, file removal,
provider deletion, recovery change or credential rotation occurs. Client rollback
alone does not revoke existing Nextcloud sessions/app passwords; keep a reviewed
subject roster and measure actual revocation behavior in live acceptance.

## Verification limits

Actual Ansible runs against synthetic kubectl/occ and HTTPS Keycloak fixtures
exercise default/check noncontact, identity conflicts, idempotence, interrupted
copy/revocation, owner versus household admin denial, discovery failure, exact
image rendering and recovery preservation. PHP verification helpers are read-only
and default off. Real signed-token/browser/state/nonce tests, certificate integrity,
Pod/CNI/NAT behavior, native account/session revocation, image execution and paired
backup/restore still need independently approved acceptance. Do not import household
data based on offline passes.

The callback path defaults to `/index.php/apps/user_oidc/code`. If actual native
routing uses pretty URLs, explicitly review `/apps/user_oidc/code` instead via
`nextcloud_sso_callback_path` in BOTH client and native inputs. Only these two
exact paths are accepted, never a wildcard or both callbacks. During apply and
activate, the verifier requests the unauthenticated browser-facing provider login
at the exact Nextcloud origin with the verified numeric provider ID. It requires
trusted HTTPS using `nextcloud_ca_file`, does not follow redirects or retain
cookies, and checks the returned authorization endpoint, client, S256 and exact
callback before activation. The operator must be able to reach that origin and
supply the public CA file, including on apply/activate. Failures are redacted.

CLI route generation is not evidence of the browser callback: `OC_CONSOLE` may
include `/index.php` even when real HTTP routing emits a pretty URL. Keep
`overwrite.cli.url` canonical, but choose the single callback from actual HTTP
behavior. Correct BOTH operator inputs and the guarded Keycloak registration
through their separately approved lifecycle, not by registering both paths.
This source-only verifier change needs no Nextcloud image rebuild or app redeploy.
It does not perform a user login or prove account/admin access.

## Confirmed owner and future household access

Corey's existing Keycloak identity is intended to retain platform-admin authority
and receive native admin for this dedicated Nextcloud tenant. Use its verified
immutable subject for the direct owner role and separate native grant; no new
identity, username/email linking or inferred platform-group mapping. Keep the
existing local Nextcloud admin unchanged for independent recovery. Live acceptance
must prove both Corey's actual native admin access and retained platform access,
then prove local recovery independently.

Jett is the intended ordinary household user, without native admin. Do not create
or enroll that account now. Any future household grant needs separate approval,
exact subject verification and successful ordinary-access/admin-denial tests.
Recording this design does not authorize activation, credentials or live grants;
all example run flags and subject selections remain disabled/empty.

## Published image rollout candidate

`gitops/base/app-values.yaml` now selects the exact private image recorded in
`published-image.json` for web, same-Pod cron and initialization. Publication run
[42339875502](https://github.com/perkforge/perkforge-tenant-nextcloud/actions/runs/42339875502)
verified the reviewed image ID after pulling its immutable registry digest. The
recorded scan findings remain accepted only for this image; it is not a clean scan.
The chart references only `nextcloud-registry-existing` for private pulls and
mounts only the existing named OIDC client-secret/public CA read-only. Local values
set the canonical HTTPS CLI origin. This does not install/enable user_oidc, create
a provider, allow private HTTP, change recovery login, create credentials or grant users.

Before selecting a new app release, separately review and publish the matching
tenant policy, then approve its exact application. Deliver the private pull Secret,
`nextcloud-oidc` and `nextcloud-oidc-ca` using approved operator-owned inputs; never
reuse a publisher token or commit credentials. Those inputs do not currently exist
in the live namespace. Do not select this image before all three are verified.
Select the released app through enrollment/platform pins, not a live-only image patch.
The retained database/files claims, UID33, database TLS, web/cron budgets, local admin
and current network boundary are unchanged by this source candidate.

Before rollout, verify local recovery login and record current Pod/claim identities
and synthetic-file checksum. After the approved Recreate rollout, verify both
containers Ready, exact running digest, database TLS, retained data and two successful
cron runs. Stop on failure and preserve resources. Native app preparation, dedicated
Keycloak client, narrow issuer egress/trust, provider setup, owner login and the
separate native-admin grant still require their own approved checks. Jett/household
onboarding remains deferred. No merge, image publication or test run enables SSO.
