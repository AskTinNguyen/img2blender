from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import geometry_invariants as invariants


def contract():
    return {"referenceAnalysis": {"observedFeatures": [{"id": "f1"}]}, "geometryInvariants": [
        {"id": "pane-size", "featureId": "f1", "measurement": "pane", "kind": "dimensions",
         "targets": ["LeftPane", "RightPane"], "frame": "object-local",
         "expected": [1, 2, 0.05], "tolerance": 0.001, "applicablePasses": ["secondary-form"]}
    ]}


def evidence(spec):
    row = spec["geometryInvariants"][0]
    return {"schemaVersion": 2, "checkpointSha256": "a" * 64, "specSha256": "b" * 64,
            "passId": "secondary-form", "errors": [], "results": [invariants.result_for(
                row, {target: row["expected"][:] for target in row["targets"]})]}


class InvariantTests(unittest.TestCase):
    def setUp(self):
        self.spec = contract()
        self.row = self.spec["geometryInvariants"][0]
        self.report = evidence(self.spec)

    def validate(self):
        invariants.validate_invariant_report(self.report, self.spec, "a" * 64, "b" * 64, "secondary-form")

    def test_valid_and_absent_contract(self):
        self.assertEqual(invariants.validate_invariants({}), [])
        self.assertEqual(invariants.validate_invariants(self.spec), [])
        self.validate()

    def test_final_delivery_cannot_skip_declared_invariants(self):
        self.assertEqual([], invariants.applicable_invariants(self.spec, "materials"))
        self.assertEqual([self.row], invariants.applicable_invariants(self.spec, "final-delivery"))
        final_report = {**self.report, "passId": "final-delivery"}
        invariants.validate_invariant_report(final_report, self.spec, "a" * 64, "b" * 64, "final-delivery")
        final_report["results"] = []
        with self.assertRaises(ValueError):
            invariants.validate_invariant_report(final_report, self.spec, "a" * 64, "b" * 64, "final-delivery")

    def test_identically_wrong_peers_do_not_pass(self):
        self.report["results"][0]["measured"] = {name: [1.1, 2, 0.05] for name in self.row["targets"]}
        self.assertTrue(self.report["results"][0]["pass"])
        with self.assertRaisesRegex(ValueError, "failed"):
            self.validate()

    def test_pane_and_opening_are_distinct_measurements(self):
        opening = {**self.row, "id": "opening", "measurement": "visible-opening", "vertexGroup": "Boundary"}
        self.spec["geometryInvariants"].append(opening)
        with self.assertRaisesRegex(ValueError, "every applicable"):
            self.validate()
        self.report["results"].append(invariants.result_for(opening, self.report["results"][0]["measured"]))
        self.validate()
        self.report["results"][1]["measurement"] = "pane"
        with self.assertRaisesRegex(ValueError, "measurement mismatch"):
            self.validate()

    def test_missing_boundary_is_rejected(self):
        self.row["measurement"] = "rough-opening"
        self.assertTrue(any("vertexGroup" in e for e in invariants.validate_invariants(self.spec)))

    def test_nonfinite_and_boolean_numbers_rejected(self):
        for value in [float("nan"), float("inf"), -float("inf"), True, False, 10 ** 1000]:
            with self.subTest(value=str(value)):
                spec = contract()
                spec["geometryInvariants"][0]["expected"][0] = value
                self.assertTrue(invariants.validate_invariants(spec))
                self.report = evidence(self.spec)
                self.report["results"][0]["measured"]["LeftPane"][0] = value
                with self.assertRaises(ValueError):
                    self.validate()

    def test_stale_hash_and_pass(self):
        for key in ["checkpointSha256", "specSha256", "passId"]:
            self.report = evidence(self.spec)
            self.report[key] = "stale"
            with self.assertRaises(ValueError):
                self.validate()

    def test_missing_duplicate_extra_or_empty_results_fail(self):
        for results in [[], [self.report["results"][0]] * 2,
                        [{**self.report["results"][0], "id": "unknown"}]]:
            self.report["results"] = results
            with self.assertRaises(ValueError):
                self.validate()

    def test_missing_or_extra_target_fails(self):
        measured = {"LeftPane": [1, 2, 0.05]}
        self.assertFalse(invariants.evaluate_invariant(self.row, measured))
        measured.update(RightPane=[1, 2, 0.05], ExtraPane=[1, 2, 0.05])
        self.assertFalse(invariants.evaluate_invariant(self.row, measured))

    def test_invalid_contract_fields_return_errors(self):
        for key, value in [("targets", []), ("targets", ["A", "A"]), ("targets", [[1]]),
                           ("tolerance", -1), ("tolerance", True), ("featureId", "missing"),
                           ("kind", []), ("measurement", {}), ("featureId", []),
                           ("applicablePasses", []), ("applicablePasses", ["intake"])]:
            with self.subTest(key=key, value=value):
                spec = contract()
                spec["geometryInvariants"][0][key] = value
                self.assertTrue(invariants.validate_invariants(spec))

    def test_count_is_exact_and_properties_are_numeric(self):
        self.row.update(kind="count", expected=2, tolerance=0)
        self.assertEqual(invariants.validate_invariants(self.spec), [])
        self.assertTrue(invariants.evaluate_invariant(self.row, 2))
        for bad in [True, 2.0, 1, 3]:
            self.assertFalse(invariants.evaluate_invariant(self.row, bad))
        self.row.update(kind="property", property="profile_depth", expected=0.12)
        self.assertEqual(invariants.validate_invariants(self.spec), [])
        self.assertTrue(invariants.evaluate_invariant(self.row, {"LeftPane": 0.12, "RightPane": 0.12}))
        self.row["expected"] = "looks like reference"
        self.assertTrue(invariants.validate_invariants(self.spec))

    def test_failed_complete_evidence_can_be_recorded_without_progress(self):
        result = self.report["results"][0]
        result["measured"] = {name: [1.1, 2, 0.05] for name in self.row["targets"]}
        result["pass"] = False
        self.report["errors"] = ["invariant pane-size failed its declared expectation"]
        with self.assertRaises(ValueError):
            self.validate()
        invariants.validate_invariant_report(self.report, self.spec, "a" * 64, "b" * 64,
                                              "secondary-form", require_pass=False)
        result["pass"] = True
        with self.assertRaises(ValueError):
            invariants.validate_invariant_report(self.report, self.spec, "a" * 64, "b" * 64,
                                                  "secondary-form", require_pass=False)
        result["pass"] = False
        result["measured"]["LeftPane"] = [float("nan"), 2, 0.05]
        with self.assertRaisesRegex(ValueError, "malformed"):
            invariants.validate_invariant_report(self.report, self.spec, "a" * 64, "b" * 64,
                                                  "secondary-form", require_pass=False)

    def test_rotation_samples_recomputed(self):
        self.row.update(kind="rotation", measurement="rig", expected=[0, 0, 0], samples=[
            {"controlObject": "Control", "inputProperty": "angle", "inputValue": 0.5, "expected": [0, 0, 0.5]}])
        measured = {name: [0, 0, 0] for name in self.row["targets"]}
        sampled = [{name: [0, 0, 0.5] for name in self.row["targets"]}]
        self.report["results"] = [invariants.result_for(self.row, measured, sampled)]
        self.validate()
        sampled[0]["LeftPane"] = [0, 0, 0]
        with self.assertRaisesRegex(ValueError, "failed"):
            self.validate()


BLENDER = shutil.which("blender") or ("/Applications/Blender.app/Contents/MacOS/Blender"
    if Path("/Applications/Blender.app/Contents/MacOS/Blender").exists() else None)


@unittest.skipUnless(BLENDER, "Blender executable unavailable")
class BlenderAdapterTests(unittest.TestCase):
    def test_actual_vertices_modifiers_frames_and_driver_samples(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            fixture = subprocess.run([BLENDER, "--background", "--factory-startup", "--python-exit-code", "1", "--python",
                                      str(ROOT / "tests" / "blender_invariant_fixture.py"), "--", str(root)],
                                     capture_output=True, text=True, timeout=90)
            self.assertEqual(fixture.returncode, 0, fixture.stdout + fixture.stderr)
            spec = json.loads((root / "spec.json").read_text())
            for variant in ("valid", "wrong-opening", "missing-target", "missing-group", "wrong-driver"):
                with self.subTest(variant=variant):
                    current = copy.deepcopy(spec)
                    rows = current["geometryInvariants"]
                    if variant == "wrong-opening":
                        rows[1]["expected"] = [4, 4, 0]
                    elif variant == "missing-target":
                        rows[0]["targets"] = ["MissingPane"]
                    elif variant == "missing-group":
                        rows[1]["vertexGroup"] = "MissingBoundary"
                    elif variant == "wrong-driver":
                        rows[3]["samples"][0]["expected"] = [0, 0, 1]
                    (root / "spec.json").write_text(json.dumps(current))
                    result = subprocess.run([BLENDER, "--background", str(root / "fixture.blend"),
                                             "--python-exit-code", "1", "--python",
                                             str(ROOT / "scripts" / "check_geometry_invariants.py"), "--",
                                             "--spec", str(root / "spec.json"), "--pass-id", "secondary-form",
                                             "--out", str(root / "report.json")], capture_output=True, text=True, timeout=90)
                    report = json.loads((root / "report.json").read_text())
                    if variant == "valid":
                        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                        invariants.validate_invariant_report(report, current,
                            hashlib.sha256((root / "fixture.blend").read_bytes()).hexdigest(),
                            hashlib.sha256((root / "spec.json").read_bytes()).hexdigest(), "secondary-form")
                    else:
                        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
                        self.assertTrue(report["errors"])


if __name__ == "__main__":
    unittest.main()
