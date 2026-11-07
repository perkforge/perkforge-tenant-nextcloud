# Exact reviewed image promotion

This manual workflow promotes **only review run #2**, source
`9d73c5d358234c3caa5e5f0ff0e3c8ddae4325ef`, to
`ghcr.io/perkforge/nextcloud-sso:35.0.2-oidc8.13.0`.
It does not rebuild, patch, relabel, enable SSO, select a release pin, change package
visibility, create a persistent credential, or deploy. The scanned archive is
loaded unchanged; its image ID must survive the registry round trip.

The recorded Trivy scan contains findings. Publication approval for this exact
image is not a clean-scan claim or standing acceptance for future images. Preserve
the separate scan report/SBOM and triage findings before a later hardened release.

## Review and dispatch

1. Review/merge this source PR. Neither the merge nor PR CI publishes anything.
2. Confirm the GHCR destination remains **private** and belongs to this repository.
   Existing public/internal or differently linked packages are refused.
3. An organization owner must ensure no other publisher can write this target
   tag during promotion, then select `exclusive_tag_publication=true` and
   `publish=true` in `sso-image-promote` on `main`. The workflow cannot enforce
   exclusion of other tokens or publishers and otherwise stays disabled.
   Leave `owner_verified_new_package=false` for an existing readable private package.
   For first publication, an organization owner must independently check the full
   organization package inventory and verify that `nextcloud-sso` does not exist.
   Only after that check may they select `owner_verified_new_package=true` to
   authorize new private creation. An API 404, a missing target tag, or inability
   to inspect the organization is **not** proof of absence. Stop if uncertain.
   GitHub creates new GHCR packages private by default. The acknowledgment is a
   human prerequisite, not a claim that the workflow verified nonexistence.
   The workflow rejects visible existing images whose package metadata is unreadable.
4. The workflow checks the source run/artifact identity, expiration, ZIP checksum,
   inner image checksum, source commit, exact image ID and Linux/amd64 platform.
   After loading and checking the archive, it checks the destination immediately
   before push and refuses any observed conflicting tag.
5. Publication uses only the job's short-lived `GITHUB_TOKEN`, with
   `contents:read`, `actions:read` and `packages:write`. No PAT, credential
   enrollment, cluster access, package permission change or visibility API is used.
6. Read the successful publication receipt and actual registry manifest digest.
   New package privacy is verified immediately after the initial push; existing
   package privacy is checked before push and again afterward. An unavailable or
   unexpected visibility result blocks success, and is not automatically repaired.
   The digest is also pulled back and its image ID checked against the scanned ID.

The ZIP and image checksums in `reviewed-image.json` are not registry manifest
digests. The workflow records the latter after publication. The registry does not
enforce immutable tags; serialized workflow runs and conflicting-tag checks
prevent ordinary accidental overwrites but cannot make an external publisher's
concurrent tag changes atomic. Do not publish this tag concurrently by another route.

The source artifact expires on **2026-11-14 at 04:00:52 UTC**. An expired/missing
artifact is a stop condition, not permission to rebuild or substitute another run.
A failed push has a potentially partial outcome. Inspect the same target and rerun
the same reviewed workflow only after understanding the failure; the workflow has
no automatic write retries and rechecks an existing tag for the exact image.
Do not change visibility or grant unrelated repository/package access to fix errors.

The separate platform-owned read-only image-pull credential and namespaced
imagePullSecret, exact-digest admission/release selection, credentials and SSO
activation remain independently reviewed work.
