# Disabled Nextcloud SSO preparation

No selected values, hooks, image pins or Flux inputs change. `prepare.yaml` only
assembles a fresh offline image context from an already downloaded public artifact.
Default and Ansible check mode do not read the artifact or contact any endpoint:

```sh
ansible-playbook sso/prepare.yaml
ansible-playbook sso/prepare.yaml --check -e nextcloud_sso_prepare=true
ansible-playbook sso/prepare.yaml -e nextcloud_sso_prepare=true \
  -e nextcloud_sso_archive=/absolute/user_oidc-v8.13.0.tar.gz \
  -e nextcloud_sso_output=/absolute/fresh-review-context
```

Fetch the exact URL in artifact.yaml through an approved workstation connection;
the play verifies its published SHA256 before copying. Dockerfile repeats the
check and places the signed built app under `/opt/perkforge/apps`, outside the
persistent custom_apps directory and Nextcloud's automatic initialization source.
No app-store call, runtime download, automatic installation or app enable occurs.
The built artifact includes dependencies and Nextcloud signature metadata.
Review the signature with Nextcloud integrity checking before any enable operation.
This is a reproducible build recipe, not a claim of bit-identical OCI image bytes.

## Publication and activation gates

Build/test/publish a separate candidate image only after review. Record its actual
immutable digest, provenance/SBOM and vulnerability review. Enrollment currently
admits exactly the existing image and public config volumes: it must continue to
reject this candidate. A later reviewed exact-digest/mount/config change, a bounded
copy into persistent custom_apps, signature verification, provider creation and
separate activation are still required. Do not loosen admission to wildcards,
add a runtime fetch or overwrite an existing installed app. Failed/interrupted
preparation preserves its output; repeat with a fresh directory. Repeating a
completed preparation into the same directory refuses rather than overwriting it.

The platform PR renders the disabled own-client and deny-all provider review
inputs. Enrollment renders unselected exact issuer egress/public trust. Neither
is an active native adapter. Installation, provider conflict/idempotence handling,
private-secret delivery and lifecycle apply/activate/rollback remain explicit
implementation gates before production use. Do not run `occ app:install` against
the app store or bootstrap users as a shortcut.

Keep local login (`allow_multiple_user_backends=1`), existing recovery credentials,
files/database and all other apps. Never recreate a provider: its numeric ID is
part of stable user and group identity. See the platform SSO Nextcloud runbook for
subject/provisioning/admin decisions and required real acceptance. No household
data, backup or restore readiness is claimed.
