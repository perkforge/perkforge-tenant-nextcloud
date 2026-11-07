"""Offline promotion checks. No GitHub, registry, Docker daemon or cluster calls."""
import copy
from contextlib import ExitStack, redirect_stdout
import os
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile
import yaml

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("promotion", ROOT / "scripts/promote_sso_image.py")
P = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(P)
C = json.loads((ROOT / "sso/reviewed-image.json").read_text())


class PromotionGuards(unittest.TestCase):
    def source(self):
        workflow = {"id": C["source_run_id"], "repository": {"full_name": C["repository"]},
                    "head_sha": C["source_commit"], "head_branch": "main",
                    "event": "workflow_dispatch", "path": C["source_workflow"],
                    "status": "completed", "conclusion": "success"}
        artifact = {"id": C["artifact_id"], "name": C["artifact_name"], "expired": False,
                    "digest": "sha256:" + C["artifact_zip_sha256"],
                    "workflow_run": {"id": C["source_run_id"], "head_sha": C["source_commit"]}}
        return workflow, artifact

    def test_exact_successful_source(self):
        P.verify_source(C, *self.source())

    def test_wrong_source_and_non_success_refused(self):
        for change in [{"head_sha": "f"*40}, {"head_branch": "other"}, {"event": "pull_request"},
                       {"conclusion": "failure"}, {"status": "in_progress"}, {"path": "other.yml"},
                       {"id": 1}, {"repository": {"full_name": "foreign/repo"}}]:
            workflow, artifact = self.source()
            workflow.update(change)
            with self.subTest(change=change), self.assertRaises(RuntimeError):
                P.verify_source(C, workflow, artifact)

    def test_expired_changed_and_foreign_artifact_refused(self):
        for change in [{"expired": True}, {"id": 1}, {"name": "other"}, {"digest": "sha256:"+"f"*64},
                       {"workflow_run": {"id": 1, "head_sha": C["source_commit"]}}]:
            workflow, artifact = self.source()
            artifact.update(change)
            with self.subTest(change=change), self.assertRaises(RuntimeError):
                P.verify_source(C, workflow, artifact)

    def test_existing_package_must_be_private_and_owned(self):
        valid = {"visibility": "private", "name": C["package_name"],
                 "repository": {"full_name": C["repository"]}}
        with patch.object(P, "api", return_value=(200, valid)):
            self.assertEqual(P.private_package(C), "private")
        for change in [{"visibility": "public"}, {"visibility": "internal"},
                       {"name": "other"}, {"repository": {"full_name": "foreign/repo"}}, {"repository": {}}]:
            with patch.object(P, "api", return_value=(200, {**valid, **change})):
                with self.subTest(change=change), self.assertRaises(RuntimeError):
                    P.private_package(C, True)

    def test_missing_or_unreadable_needs_explicit_bootstrap(self):
        with patch.object(P, "api", return_value=(404, {})):
            with self.assertRaises(RuntimeError):
                P.private_package(C)
            self.assertEqual(P.private_package(C, True), "new-private-requested")

    def test_manifest_exact_image_only(self):
        good = {"schemaVersion": 2, "config": {"digest": C["image_id"]}}
        P.verify_manifest(good, C)
        for bad in [{}, {**good, "config": {"digest": "sha256:"+"f"*64}},
                    {**good, "manifests": []}]:
            with self.subTest(manifest=bad), self.assertRaises(RuntimeError):
                P.verify_manifest(bad, C)

    def test_registry_denials_are_not_tag_absence(self):
        from subprocess import CompletedProcess
        for error in ["unauthorized: manifest unknown", "denied: not found",
                      "forbidden", "certificate failure", "timeout", "unknown failure"]:
            with patch.object(P.subprocess, "run", return_value=CompletedProcess([], 1, "", error)):
                with self.subTest(error=error), self.assertRaises(RuntimeError):
                    P.remote_manifest(C["destination"])
        with patch.object(P.subprocess, "run", return_value=CompletedProcess([], 1, "", "manifest unknown")):
            self.assertIsNone(P.remote_manifest(C["destination"]))

    def bundle(self, directory, changes=None):
        image = b"synthetic image archive"
        contract = copy.deepcopy(C)
        contract["image_archive_sha256"] = hashlib.sha256(image).hexdigest()
        members = {"image.tar": image, "image.tar.sha256": contract["image_archive_sha256"]+"  image.tar\n",
                   "source-commit": C["source_commit"]+"\n", "artifact.yaml": "version: 8.13.0\n",
                   "image-inspect.json": json.dumps([{"Id": C["image_id"], "Os": "linux", "Architecture": "amd64"}])}
        members.update(changes or {})
        path = directory / "input.zip"
        with zipfile.ZipFile(path, "w") as archive:
            for name, data in members.items():
                archive.writestr(name, data)
        contract["artifact_zip_sha256"] = P.sha256(path)
        return path, contract

    def test_bundle_checksums_source_image_platform(self):
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            path, contract = self.bundle(directory)
            P.verify_bundle(path, directory, contract)
        mutations = [{"source-commit": "wrong"}, {"image.tar": b"wrong"}, {"image.tar.sha256": "wrong"},
                     {"image-inspect.json": json.dumps([{"Id": C["image_id"], "Os": "linux", "Architecture": "arm64"}])},
                     {"../escape": "bad"}]
        for change in mutations:
            with tempfile.TemporaryDirectory() as temp:
                directory = Path(temp)
                path, contract = self.bundle(directory, change)
                with self.subTest(change=change), self.assertRaises(RuntimeError):
                    P.verify_bundle(path, directory, contract)

    def test_changed_zip_rejected_before_extract(self):
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            path, contract = self.bundle(directory)
            path.write_bytes(path.read_bytes()+b"changed")
            with self.assertRaises(RuntimeError):
                P.verify_bundle(path, directory, contract)
            self.assertFalse((directory/"image.tar").exists())

    def test_workflow_manual_default_off_and_no_deployment(self):
        workflow = yaml.load((ROOT/".github/workflows/sso-image-promote.yml").read_text(), Loader=yaml.BaseLoader)
        self.assertEqual(set(workflow["on"]), {"workflow_dispatch"})
        self.assertEqual(workflow["on"]["workflow_dispatch"]["inputs"]["publish"]["default"], "false")
        self.assertEqual(workflow["on"]["workflow_dispatch"]["inputs"]["owner_verified_new_package"]["default"], "false")
        self.assertEqual(workflow["on"]["workflow_dispatch"]["inputs"]["exclusive_tag_publication"]["default"], "false")
        self.assertEqual(workflow["permissions"], {"contents": "read"})
        job = workflow["jobs"]["publish"]
        for gate in ["workflow_dispatch", "refs/heads/main", C["repository"], "inputs.publish", "inputs.exclusive_tag_publication"]:
            self.assertIn(gate, job["if"])
        self.assertEqual(job["permissions"], {"contents":"read", "actions":"read", "packages":"write"})
        steps = job["steps"]
        self.assertEqual(steps[0]["with"]["persist-credentials"], "false")
        text = (ROOT/".github/workflows/sso-image-promote.yml").read_text()
        self.assertNotIn("docker/build-push-action", text)
        self.assertNotIn("kubectl", text)
        self.assertNotIn("docker build ", (ROOT/"scripts/promote_sso_image.py").read_text())
        self.assertEqual(C["destination"], "ghcr.io/perkforge/nextcloud-sso:35.0.2-oidc8.13.0")
        self.assertEqual(C["visibility"], "private")


class PublicationOrchestration(unittest.TestCase):
    GOOD = {"schemaVersion": 2, "config": {"digest": C["image_id"]}}

    def exercise(self, manifest=None, package="private", registry_error=False,
                 package_error=False, push_error=False, post_private_error=False,
                 roundtrip_error=False, immutable_error=False):
        events = []
        package_calls = 0
        digest = "sha256:" + "a" * 64
        immutable = C["destination"].rsplit(":", 1)[0] + "@" + digest

        def check_package(*args):
            nonlocal package_calls
            package_calls += 1
            events.append(("package",))
            if package_error or (post_private_error and package_calls > 1):
                raise RuntimeError("Unreadable or non-private package")
            return package if package_calls == 1 else "private"

        def check_manifest(reference):
            events.append(("manifest", reference))
            if registry_error:
                raise RuntimeError("Unknown registry result")
            if reference == C["destination"]:
                return manifest
            return {} if immutable_error else self.GOOD

        def command(*args):
            events.append(args)
            if args[:2] == ("docker", "push") and push_error:
                raise RuntimeError("Uncertain push failure")
            if args[:3] == ("docker", "image", "inspect"):
                image_id = "wrong" if roundtrip_error and args[-1] == immutable else C["image_id"]
                return json.dumps([{"Id": image_id, "Os": "linux", "Architecture": "amd64"}])
            if args[:3] == ("docker", "buildx", "imagetools"):
                return json.dumps({"digest": digest})
            return ""

        with tempfile.TemporaryDirectory() as temp, ExitStack() as stack:
            directory = Path(temp)
            stack.enter_context(patch.object(P, "sha256", return_value=C["image_archive_sha256"]))
            stack.enter_context(patch.object(P, "private_package", side_effect=check_package))
            stack.enter_context(patch.object(P, "remote_manifest", side_effect=check_manifest))
            stack.enter_context(patch.object(P, "run", side_effect=command))
            stack.enter_context(patch.object(P.time, "sleep"))
            stack.enter_context(patch.dict(os.environ, {"GITHUB_STEP_SUMMARY": ""}))
            stack.enter_context(redirect_stdout(io.StringIO()))
            error = None
            try:
                P.publish(directory, C, package == "new-private-requested")
            except RuntimeError as exception:
                error = exception
            receipt_path = directory / "publication-receipt.json"
            receipt = json.loads(receipt_path.read_text()) if receipt_path.exists() else None
        pushes = [event for event in events if event[:2] == ("docker", "push")]
        return error, events, pushes, receipt

    def test_existing_exact_tag_skips_push(self):
        error, events, pushes, receipt = self.exercise(manifest=self.GOOD)
        self.assertIsNone(error)
        self.assertEqual(pushes, [])
        self.assertEqual(receipt["image_id"], C["image_id"])

    def test_different_tag_refused_after_load_before_any_push(self):
        error, events, pushes, receipt = self.exercise(manifest={"schemaVersion": 2, "config": {"digest": "wrong"}})
        self.assertIsNotNone(error)
        self.assertEqual(pushes, [])
        self.assertIsNone(receipt)
        load_index = next(i for i, event in enumerate(events) if event[:2] == ("docker", "load"))
        package_index = events.index(("package",))
        manifest_index = events.index(("manifest", C["destination"]))
        self.assertLess(load_index, package_index)
        self.assertLess(package_index, manifest_index)

    def test_private_creation_refuses_unreadable_existing_image(self):
        error, _, pushes, receipt = self.exercise(manifest=self.GOOD, package="new-private-requested")
        self.assertIsNotNone(error)
        self.assertEqual(pushes, [])
        self.assertIsNone(receipt)

    def test_unknown_destination_or_authorization_has_zero_pushes(self):
        for options in [{"registry_error": True}, {"package_error": True}]:
            with self.subTest(options=options):
                error, _, pushes, receipt = self.exercise(**options)
                self.assertIsNotNone(error)
                self.assertEqual(pushes, [])
                self.assertIsNone(receipt)

    def test_new_private_creation_checks_and_records_exact_image(self):
        error, _, pushes, receipt = self.exercise(package="new-private-requested")
        self.assertIsNone(error)
        self.assertEqual(len(pushes), 1)
        self.assertEqual(receipt["visibility"], "private")
        self.assertFalse(receipt["rebuilt"])
        self.assertFalse(receipt["deployed"])

    def test_push_failure_not_retried_or_reported_successful(self):
        error, _, pushes, receipt = self.exercise(push_error=True)
        self.assertIsNotNone(error)
        self.assertEqual(len(pushes), 1)
        self.assertIsNone(receipt)

    def test_post_push_privacy_failure_has_no_success_receipt(self):
        error, _, pushes, receipt = self.exercise(post_private_error=True)
        self.assertIsNotNone(error)
        self.assertEqual(len(pushes), 1)
        self.assertIsNone(receipt)

    def test_registry_digest_and_roundtrip_failures_have_no_receipt(self):
        for options in [{"immutable_error": True}, {"roundtrip_error": True}]:
            with self.subTest(options=options):
                error, _, pushes, receipt = self.exercise(**options)
                self.assertIsNotNone(error)
                self.assertEqual(len(pushes), 1)
                self.assertIsNone(receipt)


if __name__ == "__main__":
    unittest.main()
