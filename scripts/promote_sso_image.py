#!/usr/bin/env python3
"""Promote one reviewed archive. Never build, alter visibility, or deploy."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import time
import zipfile

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "sso/reviewed-image.json"
MEMBERS = {"artifact.yaml", "image-inspect.json", "image.tar",
           "image.tar.sha256", "source-commit"}
DIGEST = re.compile(r"^sha256:[0-9a-f]{64}$")


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def run(*args):
    result = subprocess.run(args, capture_output=True, text=True, check=False)
    require(result.returncode == 0, f"Command failed: {args[0]} {args[1]}; inspect the workflow step. No automatic write retry.")
    return result.stdout


def api(path):
    result = subprocess.run(["gh", "api", "--include", path],
                            capture_output=True, text=True, check=False)
    parts = re.split(r"\r?\n\r?\n", result.stdout, maxsplit=1)
    first = parts[0].splitlines()[0] if parts and parts[0] else ""
    match = re.match(r"HTTP/\S+ (\d{3})", first)
    require(match is not None, "GitHub API status unavailable; stop without guessing.")
    status = int(match.group(1))
    require(status in (200, 404), f"GitHub API returned HTTP {status}; stop.")
    body = json.loads(parts[1]) if len(parts) == 2 and parts[1].strip() else {}
    return status, body


def private_package(contract, allow_create=False):
    status, package = api(f"orgs/{contract['package_owner']}/packages/container/{contract['package_name']}")
    if status == 404:
        require(allow_create, "Package missing or unreadable. Stop until an organization owner independently verifies that this package does not exist and explicitly authorizes private creation.")
        # A 404 is not proof of absence. The separate default-off owner acknowledgment
        # must come from an independent organization-owner check, not this API.
        # It authorizes private creation only, never adoption/settings changes.
        return "new-private-requested"
    require(package.get("visibility") == "private", "Existing GHCR package is not private; no push or visibility change.")
    require(package.get("name") == contract["package_name"], "Wrong package.")
    require(package.get("repository", {}).get("full_name") == contract["repository"],
            "Existing package is not linked to this repository; no adoption or permission changes.")
    return "private"


def verify_source(contract, workflow, artifact):
    require(workflow.get("id") == contract["source_run_id"], "Wrong source run.")
    require(workflow.get("repository", {}).get("full_name") == contract["repository"], "Wrong source repository.")
    require(workflow.get("head_sha") == contract["source_commit"], "Wrong source commit.")
    require(workflow.get("head_branch") == "main" and workflow.get("event") == "workflow_dispatch", "Wrong source event/branch.")
    require(workflow.get("path") == contract["source_workflow"], "Wrong source workflow.")
    require(workflow.get("status") == "completed" and workflow.get("conclusion") == "success", "Source build did not succeed.")
    require(artifact.get("id") == contract["artifact_id"] and artifact.get("name") == contract["artifact_name"], "Wrong artifact.")
    require(not artifact.get("expired", True), "Review artifact expired. Do not rebuild or substitute it.")
    require(artifact.get("digest") == "sha256:" + contract["artifact_zip_sha256"], "Wrong artifact ZIP digest.")
    source = artifact.get("workflow_run", {})
    require(source.get("id") == contract["source_run_id"] and source.get("head_sha") == contract["source_commit"], "Artifact provenance mismatch.")


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(8 * 1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def verify_bundle(path, directory, contract):
    require(sha256(path) == contract["artifact_zip_sha256"], "Downloaded ZIP checksum mismatch.")
    with zipfile.ZipFile(path) as archive:
        require(set(archive.namelist()) == MEMBERS and len(archive.infolist()) == len(MEMBERS), "Unexpected archive members.")
        for name in MEMBERS:
            info = archive.getinfo(name)
            require(info.file_size < 2_000_000_000, "Oversized archive member.")
            # Fixed basenames only: never extract archive-provided paths.
            with archive.open(name) as source, (directory / name).open("wb") as target:
                while chunk := source.read(8 * 1024 * 1024):
                    target.write(chunk)
    require((directory / "source-commit").read_text().strip() == contract["source_commit"], "Packaged source mismatch.")
    require(sha256(directory / "image.tar") == contract["image_archive_sha256"], "Image archive checksum mismatch.")
    require((directory / "image.tar.sha256").read_text().split()[0] == contract["image_archive_sha256"], "Packaged image checksum mismatch.")
    image = json.loads((directory / "image-inspect.json").read_text())
    require(len(image) == 1 and image[0].get("Id") == contract["image_id"], "Packaged image ID mismatch.")
    require(image[0].get("Os") == "linux" and image[0].get("Architecture") == "amd64", "Unexpected image platform.")


def remote_manifest(reference):
    result = subprocess.run(["docker", "buildx", "imagetools", "inspect", "--raw", reference],
                            capture_output=True, text=True, check=False)
    if result.returncode:
        error = result.stderr.lower()
        require(not any(word in error for word in ["denied", "unauthorized", "forbidden", "timeout", "certificate"]),
                "Registry authorization/network failure; not evidence of an absent tag.")
        require("manifest unknown" in error or "not found" in error, "Registry outcome unknown; no push.")
        return None
    return json.loads(result.stdout)


def verify_manifest(manifest, contract):
    require(manifest.get("schemaVersion") == 2 and "manifests" not in manifest,
            "Unexpected registry manifest; no overwrite.")
    require(manifest.get("config", {}).get("digest") == contract["image_id"],
            "Existing/published tag differs from reviewed image; no overwrite.")


def prepare(directory, contract, allow_create):
    private_package(contract, allow_create)
    prefix = f"repos/{contract['repository']}/actions"
    run_status, workflow = api(f"{prefix}/runs/{contract['source_run_id']}")
    artifact_status, artifact = api(f"{prefix}/artifacts/{contract['artifact_id']}")
    require(run_status == artifact_status == 200, "Exact reviewed source/artifact unavailable.")
    verify_source(contract, workflow, artifact)
    directory.mkdir(mode=0o700, parents=True, exist_ok=False)
    path = directory / "review.zip"
    with path.open("wb") as output:
        result = subprocess.run(["gh", "api", f"{prefix}/artifacts/{contract['artifact_id']}/zip"],
                                stdout=output, stderr=subprocess.PIPE, check=False)
    require(result.returncode == 0, "Artifact download failed; no publication.")
    verify_bundle(path, directory, contract)


def publish(directory, contract, allow_create):
    # Load and verify first, then recheck package/tag immediately before any push.
    # External publishers must be excluded; GHCR has no atomic create-if-absent.
    require(sha256(directory / "image.tar") == contract["image_archive_sha256"], "Prepared image changed.")
    destination = contract["destination"]
    run("docker", "load", "--input", str(directory / "image.tar"))
    loaded = json.loads(run("docker", "image", "inspect", contract["image_id"]))[0]
    require(loaded["Id"] == contract["image_id"] and loaded["Os"] == "linux" and loaded["Architecture"] == "amd64",
            "Loaded image identity/platform mismatch.")
    package_state = private_package(contract, allow_create)
    manifest = remote_manifest(destination)
    if package_state == "new-private-requested":
        require(manifest is None, "An existing registry image is not readable through package metadata; no adoption.")
    if manifest is not None:
        verify_manifest(manifest, contract)
    if manifest is None:
        run("docker", "tag", contract["image_id"], destination)
        run("docker", "push", destination)  # Exactly one push attempt. Never rebuild.
    # New GHCR packages are private by default. No API changes visibility.
    # Verify that result before reporting success or offering deployment inputs.
    for attempt in range(5):
        try:
            private_package(contract, False)
            break
        except RuntimeError:
            if attempt == 4:
                raise
            time.sleep(2)
    manifest_info = json.loads(run("docker", "buildx", "imagetools", "inspect",
                                  destination, "--format", "{{json .Manifest}}"))
    digest = manifest_info.get("digest", "")
    require(bool(DIGEST.fullmatch(digest)), "Registry digest unavailable.")
    repository = destination.rsplit(":", 1)[0]
    immutable = repository + "@" + digest
    verify_manifest(remote_manifest(immutable) or {}, contract)
    run("docker", "pull", immutable)
    pulled = json.loads(run("docker", "image", "inspect", immutable))[0]
    require(pulled.get("Id") == contract["image_id"], "Registry round-trip changed the reviewed image.")
    receipt = {"source_commit": contract["source_commit"], "source_run_id": contract["source_run_id"],
               "artifact_id": contract["artifact_id"], "image_archive_sha256": contract["image_archive_sha256"],
               "image_id": contract["image_id"], "tag": destination, "registry_digest": digest,
               "immutable_image": immutable, "visibility": "private", "rebuilt": False, "deployed": False}
    (directory / "publication-receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")
    if summary := os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(summary, "a") as handle:
            handle.write(f"Private reviewed image: `{immutable}`\n\nTag: `{destination}`\n\n"
                         f"Source: `{contract['source_commit']}`; review run {contract['source_run_id']}. "
                         "No rebuild, visibility change, release-pin selection or deployment.\n")
    print(json.dumps(receipt, indent=2))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("operation", choices=["prepare", "publish"])
    parser.add_argument("--directory", type=Path, required=True)
    args = parser.parse_args()
    contract = json.loads(CONTRACT.read_text())
    require(contract["visibility"] == "private", "Only private publication is supported.")
    require(bool(os.environ.get("GH_TOKEN")), "Use the job's temporary GITHUB_TOKEN, never a stored PAT.")
    require(os.environ.get("EXCLUSIVE_TAG_PUBLICATION", "false") == "true",
            "Confirm no other publisher can write this target tag during promotion.")
    allow_create = os.environ.get("OWNER_VERIFIED_NEW_PACKAGE", "false") == "true"
    if args.operation == "prepare":
        prepare(args.directory, contract, allow_create)
    else:
        publish(args.directory, contract, allow_create)


if __name__ == "__main__":
    main()
