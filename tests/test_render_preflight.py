"""Host-side preflight orchestration tests; Blender is deliberately not required."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "render_preflight.py"
spec = importlib.util.spec_from_file_location("render_preflight", SCRIPT)
preflight = importlib.util.module_from_spec(spec)
spec.loader.exec_module(preflight)


def success(device):
    return {"success": True, "effectiveDevice": device,
            "blender": {"version_string": "fixture", "build_hash": "fixture-hash"},
            "renderSettings": {"engine": "CYCLES", "device": "CPU" if device == "CPU" else "GPU",
                               "samples": 1, "resolution": [32, 32]}, "renderBytes": 120}


class RenderPreflightTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.blender = self.root / "Blender with spaces"
        self.blender.write_text("fake executable")
        self.blender.chmod(0o700)
        self.scene = self.root / "source with spaces.blend"
        self.scene.write_bytes(b"unchanged scene")
        self.out = self.root / "reports" / "manifest.json"
        self.calls = []

    def fake_run(self, reports):
        results = iter(reports)

        def run(command, **kwargs):
            self.calls.append((command, kwargs))
            outcome = next(results)
            if isinstance(outcome, Exception):
                raise outcome
            exit_code, report = outcome
            report_path = Path(command[command.index("--report") + 1])
            if isinstance(report, str):
                report_path.write_text(report)
            elif report is not None:
                report_path.write_text(json.dumps(report))
            return subprocess.CompletedProcess(command, exit_code)
        return run

    def run_preflight(self, reports, **kwargs):
        with patch.object(preflight.subprocess, "run", side_effect=self.fake_run(reports)):
            result = preflight.preflight(self.blender, self.scene, self.out, **kwargs)
        self.assertEqual(json.loads(self.out.read_text()), result)
        self.assertEqual(self.scene.read_bytes(), b"unchanged scene")
        return result

    def test_successful_cpu_is_single_isolated_attempt(self):
        result = self.run_preflight([(0, success("CPU"))], device="CPU")
        self.assertTrue(result["success"])
        self.assertTrue(result["blendUnchanged"])
        self.assertFalse(result["cpuFallback"])
        self.assertEqual(result["effectiveDevice"], "CPU")
        self.assertEqual(len(self.calls), 1)
        command, kwargs = self.calls[0]
        self.assertEqual(command[0], str(self.blender.resolve()))
        self.assertIn(str(self.scene.resolve()), command)
        self.assertIn("--factory-startup", command)
        self.assertIn("--disable-autoexec", command)
        self.assertEqual(kwargs["timeout"], 60)
        self.assertNotIn("shell", kwargs)
        self.assertFalse(Path(command[command.index("--report") + 1]).parent.exists())

    def test_gpu_crash_gets_fresh_cpu_process(self):
        report = {"success": False, "effectiveDevice": "METAL", "phase": "render"}
        result = self.run_preflight([(-11, report), (0, success("CPU"))], device="METAL")
        self.assertTrue(result["success"])
        self.assertTrue(result["cpuFallback"])
        self.assertEqual(result["attempts"][0]["exitCode"], -11)
        self.assertIn("-11", result["attempts"][0]["error"])
        self.assertEqual(result["attempts"][0]["probe"]["phase"], "render")
        self.assertEqual(result["attempts"][1]["requestedDevice"], "CPU")

    def test_gpu_timeout_gets_bounded_cpu_fallback(self):
        result = self.run_preflight([
            subprocess.TimeoutExpired("blender", 3), (0, success("CPU"))], device="CUDA", timeout=3)
        self.assertTrue(result["success"])
        self.assertTrue(result["attempts"][0]["timedOut"])
        self.assertEqual([call[1]["timeout"] for call in self.calls], [3, 3])

    def test_cpu_timeout_fails(self):
        result = self.run_preflight([subprocess.TimeoutExpired("blender", 1)], device="CPU", timeout=1)
        self.assertFalse(result["success"])
        self.assertTrue(result["attempts"][0]["timedOut"])
        self.assertIsNone(result["effectiveDevice"])

    def test_malformed_and_incomplete_gpu_reports_trigger_fallback(self):
        for broken in ("not json", "[]", '{"success":true}', '{"success":"true"}',
                       '{"success":true,"renderBytes":"bad"}'):
            with self.subTest(report=broken):
                result = self.run_preflight([(0, broken), (0, success("CPU"))], device="OPTIX")
                self.assertTrue(result["success"])
                self.assertIn("malformed", result["attempts"][0]["error"])

    def test_failed_gpu_and_failed_cpu_do_not_pass(self):
        result = self.run_preflight([(2, {"success": False, "error": "no GPU"}),
                                     (0, {"success": False, "error": "render failed"})])
        self.assertFalse(result["success"])
        self.assertIsNone(result["effectiveDevice"])
        self.assertEqual(result["attempts"][1]["error"], "render failed")

    def test_success_report_with_nonzero_exit_does_not_pass(self):
        result = self.run_preflight([(-6, success("METAL")), (0, success("CPU"))], device="METAL")
        self.assertEqual(result["effectiveDevice"], "CPU")
        self.assertFalse(result["attempts"][0]["success"])

    def test_no_default_workaround_and_only_allowlisted_env_in_manifest(self):
        fixture_env = {"PATH": "/fixture", "PRIVATE_TOKEN": "must-not-appear"}
        with patch.dict(os.environ, fixture_env, clear=True):
            result = self.run_preflight([(0, success("CPU"))], device="CPU")
        self.assertEqual(result["cyclesEnvironment"], {})
        self.assertNotIn("must-not-appear", json.dumps(result))
        for name in preflight.CYCLES_ENV:
            self.assertNotIn(name, self.calls[-1][1]["env"])

    def test_explicit_workaround_is_process_local_and_recorded(self):
        key = "CYCLES_METAL_SPECIALIZATION_LEVEL"
        with patch.dict(os.environ, {key: "1"}):
            result = self.run_preflight([(0, success("CPU"))], device="CPU", cycles_env={key: "0"})
            self.assertEqual(os.environ[key], "1")
        self.assertEqual(self.calls[-1][1]["env"][key], "0")
        self.assertEqual(result["cyclesEnvironmentOverrides"], {key: "0"})
        self.assertEqual(result["cyclesEnvironment"][key], "0")

    def test_rejects_arbitrary_env_and_nonfinite_timeout_and_source_overwrite(self):
        for kwargs in ({"cycles_env": {"PRIVATE_TOKEN": "value"}}, {"timeout": float("nan")},
                       {"timeout": float("inf")}, {"timeout": 0}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                preflight.preflight(self.blender, self.scene, self.out, **kwargs)
        with self.assertRaises(ValueError):
            preflight.preflight(self.blender, self.scene, self.scene)


if __name__ == "__main__":
    unittest.main()
