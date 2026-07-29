from __future__ import annotations

import copy
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
import shutil
from pathlib import Path

from PIL import Image


SKILL_ROOT = Path(__file__).resolve().parents[1]
PIPELINE = SKILL_ROOT / "scripts" / "reconstruction_pipeline.py"
COMPARISONS = SKILL_ROOT / "scripts" / "build_review_comparisons.py"
FIXTURES = Path(__file__).parent / "fixtures"

sys.path.insert(0, str(SKILL_ROOT / "scripts"))
import reconstruction_pipeline as pipeline  # noqa: E402


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class PipelineTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name)
        self.reference = self.root / "reference.png"
        self.reference.write_bytes(b"reference-fixture")

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def run_cli(self, *args: str, expected: int = 0) -> subprocess.CompletedProcess[str]:
        result = subprocess.run(
            [sys.executable, str(PIPELINE), *map(str, args)],
            text=True,
            capture_output=True,
            check=False,
        )
        if result.returncode != expected:
            self.fail(
                f"command returned {result.returncode}, expected {expected}\n"
                f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
            )
        return result

    def initialize(self, complexity: str = "complex") -> tuple[Path, Path]:
        project = self.root / "project"
        self.run_cli(
            "init",
            "--project-dir",
            project,
            "--name",
            "fixture prop",
            "--reference",
            self.reference,
            "--complexity",
            complexity,
            "--subject-route",
            "hard-surface-prop",
        )
        state_path = project / "reconstruction-state.json"
        spec_path = project / "reconstruction-spec.json"
        self.fill_valid_spec(state_path, spec_path, complexity)
        return state_path, spec_path

    def fill_valid_spec(self, state_path: Path, spec_path: Path, complexity: str) -> None:
        spec = json.loads(spec_path.read_text(encoding="utf-8"))
        count = pipeline.DETAIL_MINIMUMS[complexity]
        spec["referenceAnalysis"] = {
            "suitability": "pass",
            "classification": {
                "primaryType": "specific hard-surface fixture",
                "domain": "object",
                "confidence": 0.9,
            },
            "observations": [
                "Observed length-to-height ratio is 2.0.",
                "Observed flattened rear cross-section.",
                "Observed asymmetric front notch.",
                "Observed directional brushed finish.",
            ],
            "observedFeatures": [
                {
                    "id": f"feature-{index + 1:02d}",
                    "particular": f"Observed particular feature {index + 1:02d}",
                    "evidenceRefs": ["ref-01"],
                    "confidence": 0.9,
                }
                for index in range(count)
            ],
            "inferences": [],
            "cameraEvidence": {"lensFamily": "normal"},
            "scaleEvidence": {"known": False},
            "contradictions": [],
        }
        spec["componentPlan"] = [
            {
                "id": "body",
                "name": "Specific body",
                "parentId": None,
                "topologyClass": "assembled-solid",
                "modelingRoute": "profile loft plus bevel",
                "evidenceRefs": ["ref-01"],
                "confidence": 0.9,
            }
        ]
        spec["materialPlan"] = [
            {
                "id": "body-metal",
                "componentIds": ["body"],
                "channels": {
                    "baseColor": "painted gray",
                    "roughness": "directional 0.32-0.45",
                    "normalOrHeight": "micro brushing only",
                },
                "evidenceRefs": ["ref-01"],
                "confidence": 0.85,
            }
        ]
        spec["featureContract"] = []
        for index in range(count):
            feature_id = f"feature-{index + 1:02d}"
            critical = index == 0
            spec["featureContract"].append(
                {
                    "featureId": feature_id,
                    "observedParticular": f"Observed particular feature {index + 1:02d}",
                    "implementation": {
                        "kind": "geometry",
                        "target": f"body.mesh_feature_{index + 1:02d}",
                    },
                    "subjectChecklistItems": ["profile-cross-sections"],
                    "reviewCameras": (
                        ["reference-match", f"critical-closeup:{feature_id}"]
                        if critical
                        else ["reference-match"]
                    ),
                    "confidence": 0.9,
                    "evidenceRefs": ["ref-01"],
                    "critical": critical,
                }
            )
        spec["detailInventory"] = {
            "scanMethod": "component grid",
            "minimum": count,
            "items": [
                {
                    "id": f"detail-{index + 1:02d}",
                    "kind": "profile",
                    "region": "body",
                    "affects": "identity",
                    "evidenceRef": "ref-01",
                    "mapsTo": f"body.mesh_feature_{index + 1:02d}",
                    "confidence": 0.9,
                }
                for index in range(count)
            ],
        }
        spec["unknowns"] = [
            {
                "region": "hidden underside",
                "impact": "low",
                "disposition": "infer-by-continuity",
                "confidence": 0.6,
            }
        ]
        required_views = list(pipeline.BASE_VIEW_ROLES)
        required_views.append("critical-closeup:feature-01")
        spec["qualityContract"] = {
            "definitionOfDone": [
                "Specific profile and cross-section survive matched and orbit views."
            ],
            "criticalFeatures": [
                {
                    "id": "feature-01",
                    "description": "Specific flattened profile",
                    "evidenceRefs": ["ref-01"],
                    "threshold": 0.85,
                    "passes": ["camera-match"],
                }
            ],
            "requiredViews": required_views,
            "backReviewRequired": False,
            "failureModes": ["Reference-only geometry illusion"],
            "deliverables": ["versioned blend"],
            "globalThreshold": 0.82,
            "criticalThreshold": 0.85,
        }
        write_json(spec_path, spec)
        self.run_cli("validate", state_path)

    def admit_intake(self, state_path: Path, spec_path: Path) -> None:
        self.run_cli(
            "review",
            state_path,
            "--pass-id",
            "intake",
            "--action",
            "continue",
            "--summary",
            "Validated exact reconstruction contract.",
            "--artifact",
            spec_path,
        )

    def evidence(self) -> tuple[list[str], list[str], list[dict]]:
        render_args: list[str] = []
        comparison_args: list[str] = []
        report_views: list[dict] = []
        roles = dict(pipeline.BASE_VIEW_ROLES)
        roles["critical-closeup:feature-01"] = "render"
        for role, kind in roles.items():
            path = self.root / "evidence" / f"{role.replace(':', '-')}.png"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(f"{role}-evidence".encode())
            report_views.append(
                {
                    "role": role,
                    "kind": kind,
                    "path": str(path.resolve()),
                    "judgeable": True,
                    "notes": f"{role} is legible.",
                }
            )
            target = render_args if kind == "render" else comparison_args
            target.extend([f"--{kind}", f"{role}={path}"])
        return render_args, comparison_args, report_views

    def critic_report(
        self,
        critic_id: str,
        context_id: str,
        action: str,
        score: float,
        delta: float | None,
        finding_id: str,
        views: list[dict],
    ) -> dict:
        report = json.loads(
            (FIXTURES / "critic-report-v2.json").read_text(encoding="utf-8")
        )
        report["critic"]["id"] = critic_id
        report["critic"]["contextId"] = context_id
        report["decision"] = action
        report["viewEvidence"] = copy.deepcopy(views)
        report["scorecard"]["overall"] = score
        report["scorecard"]["layers"] = {
            item: score for item in pipeline.UNIVERSAL_CHECKS
        }
        report["deltaFromPrior"]["overall"] = delta
        report["deltaFromPrior"]["summary"] = (
            "First independent round." if delta is None else f"Delta is {delta:.3f}."
        )
        report["universalChecklist"] = [
            {
                "id": item,
                "status": "pass",
                "evidenceRoles": ["reference-match"],
                "notes": f"{item} passes for the current scope.",
            }
            for item in pipeline.UNIVERSAL_CHECKS
        ]
        report["subjectChecklist"] = [
            {
                "id": item,
                "status": "pass",
                "evidenceRoles": ["reference-match", "orbit-left", "orbit-right"],
                "notes": f"{item} is supported.",
            }
            for item in pipeline.SUBJECT_CHECKS["hard-surface-prop"]
        ]
        report["hardGates"] = [
            {
                "id": item,
                "status": "pass",
                "evidenceRoles": ["reference-match", "orbit-left", "orbit-right"],
                "finding": f"{item} passes.",
            }
            for item in pipeline.MANDATORY_HARD_GATES
        ]
        report["criticalFeatures"] = [
            {
                "id": "feature-01",
                "score": 0.9,
                "visible": True,
                "supported": True,
                "attached": True,
                "freeOfIntersection": True,
                "multiViewConsistent": True,
                "onlyReferenceCamera": False,
                "evidenceRoles": [
                    "critical-closeup:feature-01",
                    "orbit-left",
                    "orbit-right",
                ],
                "notes": "Critical feature is supported in multiple views.",
            }
        ]
        report["highestImpactFinding"]["id"] = finding_id
        report["trajectory"] = {
            "status": "first-round" if delta is None else "improving",
            "rationale": "Evidence shows the stated trajectory.",
        }
        return report

    def record_round(
        self,
        state_path: Path,
        report: dict,
        render_args: list[str],
        comparison_args: list[str],
        expected: int = 0,
    ) -> subprocess.CompletedProcess[str]:
        state = json.loads(state_path.read_text(encoding="utf-8"))
        current = next(item for item in state["passes"] if item["id"] == "camera-match")
        if current.get("builderId") is None:
            start_checkpoint = self.root / "camera-start.blend"
            start_checkpoint.write_bytes(b"camera-start-checkpoint")
            start_render = self.root / "camera-start-reference.png"
            start_render.write_bytes(b"camera-start-reference-render")
            self.run_cli(
                "open-pass",
                state_path,
                "--pass-id",
                "camera-match",
                "--builder-id",
                "builder-camera",
                "--start-checkpoint",
                start_checkpoint,
                "--start-reference-render",
                start_render,
            )
            state = json.loads(state_path.read_text(encoding="utf-8"))
            current = next(
                item for item in state["passes"] if item["id"] == "camera-match"
            )
        checkpoint_record = next(
            (
                item.get("checkpoint")
                for item in reversed(current.get("corrections", []))
                if isinstance(item, dict) and item.get("checkpoint")
            ),
            None,
        )
        if checkpoint_record:
            checkpoint = Path(checkpoint_record["path"])
        else:
            checkpoint = Path(current["startCheckpoint"]["path"])

        report["contractSha256"] = state["approvedContract"]["sha256"]
        report["checkpointSha256"] = file_hash(checkpoint)
        report_path = self.root / f"{report['critic']['id']}.json"
        write_json(report_path, report)

        render_mappings = {
            render_args[index + 1].split("=", 1)[0]: Path(
                render_args[index + 1].split("=", 1)[1]
            ).resolve()
            for index in range(0, len(render_args), 2)
        }
        render_manifest = {
            "schemaVersion": 2,
            "blendFile": str(checkpoint.resolve()),
            "blendSha256": file_hash(checkpoint),
            "settings": {
                "engine": "CYCLES",
                "samples": 64,
                "seed": 230519,
                "resolution": [1024, 1024],
                "resolutionPercentage": 100,
                "viewTransform": "AgX",
                "look": "Medium High Contrast",
                "displayDevice": "sRGB",
                "exposure": 0.0,
            },
            "renders": [],
        }
        for role, path in render_mappings.items():
            role_state = {"viewLayer": "Review", "materialOverride": None, "lightRig": None}
            if role == "clay-silhouette":
                role_state["materialOverride"] = "MAT_CLAY"
            elif role == "neutral-material":
                role_state["lightRig"] = "neutral"
            elif role == "grazing-light":
                role_state["lightRig"] = "grazing"
            render_manifest["renders"].append(
                {
                    "role": role,
                    "path": str(path),
                    "sha256": file_hash(path),
                    "cameraMatrixWorld": [
                        [1, 0, 0, 0],
                        [0, 1, 0, 0],
                        [0, 0, 1, 0],
                        [0, 0, 0, 1],
                    ],
                    "cameraType": "PERSP",
                    "roleState": role_state,
                }
            )
        manifest_root = self.root / "manifests" / report["critic"]["id"]
        render_manifest_path = manifest_root / "render-manifest.json"
        write_json(render_manifest_path, render_manifest)

        comparison_mappings = {
            comparison_args[index + 1].split("=", 1)[0]: Path(
                comparison_args[index + 1].split("=", 1)[1]
            ).resolve()
            for index in range(0, len(comparison_args), 2)
        }
        reference_match = render_mappings.get("reference-match")
        prior_rounds = current.get("criticRounds", [])
        prior_reference = (
            Path(
                next(
                    item
                    for item in prior_rounds[-1]["renders"]
                    if item["role"] == "reference-match"
                )["path"]
            )
            if prior_rounds
            else Path(current["startReferenceRender"]["path"])
        )
        comparison_manifest = {
            "schemaVersion": 2,
            "inputs": {
                "reference": {
                    "path": str(self.reference.resolve()),
                    "sha256": file_hash(self.reference),
                },
                "current": {
                    "path": str(reference_match),
                    "sha256": file_hash(reference_match),
                },
                "previous": {
                    "path": str(prior_reference),
                    "sha256": file_hash(prior_reference),
                },
            },
            "evidence": [
                {
                    "role": role,
                    "kind": "comparison",
                    "path": str(path),
                    "sha256": file_hash(path),
                }
                for role, path in comparison_mappings.items()
            ],
        }
        comparison_manifest_path = manifest_root / "comparison-manifest.json"
        write_json(comparison_manifest_path, comparison_manifest)
        return self.run_cli(
            "review",
            state_path,
            "--pass-id",
            "camera-match",
            "--builder-id",
            "builder-camera",
            "--action",
            report["decision"],
            "--summary",
            "Independent visual critic verdict.",
            "--critic-report",
            report_path,
            "--checkpoint",
            checkpoint,
            "--render-manifest",
            render_manifest_path,
            "--comparison-manifest",
            comparison_manifest_path,
            *render_args,
            *comparison_args,
            expected=expected,
        )

    def correct(self, state_path: Path, finding_id: str) -> None:
        checkpoint = self.root / f"{finding_id}.blend"
        checkpoint.write_bytes(f"blend-checkpoint-{finding_id}".encode())
        self.run_cli(
            "correct",
            state_path,
            "--pass-id",
            "camera-match",
            "--builder-id",
            "builder-camera",
            "--root-cause-id",
            finding_id,
            "--summary",
            "Corrected only the named root cause.",
            "--changed",
            "body.scale_y 1.0 -> 0.94",
            "--checkpoint",
            checkpoint,
        )


class PipelineEnforcementTests(PipelineTestCase):
    def test_complex_pass_requires_two_fresh_critics_and_intervening_correction(self) -> None:
        state_path, spec_path = self.initialize("complex")
        self.admit_intake(state_path, spec_path)
        render_args, comparison_args, views = self.evidence()

        first = self.critic_report(
            "critic-round-1", "context-round-1", "refine-scene", 0.8, None, "rear-section", views
        )
        self.record_round(state_path, first, render_args, comparison_args)

        second = self.critic_report(
            "critic-round-2", "context-round-2", "continue", 0.86, 0.06, "minor-finish", views
        )
        blocked = self.record_round(
            state_path, second, render_args, comparison_args, expected=2
        )
        self.assertIn("must be corrected", blocked.stderr)

        self.correct(state_path, "rear-section")
        self.record_round(state_path, second, render_args, comparison_args)
        state = json.loads(state_path.read_text(encoding="utf-8"))
        self.assertEqual(state["currentPass"], "blockout")
        camera_pass = next(item for item in state["passes"] if item["id"] == "camera-match")
        self.assertEqual(len(camera_pass["criticRounds"]), 2)
        self.assertEqual(len(camera_pass["corrections"]), 1)

    def test_builder_cannot_be_the_critic(self) -> None:
        state_path, spec_path = self.initialize("simple")
        self.admit_intake(state_path, spec_path)
        render_args, comparison_args, views = self.evidence()
        report = self.critic_report(
            "builder-camera", "fresh-context", "continue", 0.9, None, "none", views
        )
        result = self.record_round(
            state_path, report, render_args, comparison_args, expected=2
        )
        self.assertIn("builder cannot review", result.stderr.lower())

    def test_hard_gate_overrides_high_score(self) -> None:
        state_path, spec_path = self.initialize("simple")
        self.admit_intake(state_path, spec_path)
        render_args, comparison_args, views = self.evidence()
        report = self.critic_report(
            "critic-gate", "context-gate", "continue", 0.99, None, "none", views
        )
        report["hardGates"][0]["status"] = "fail"
        report["hardGates"][0]["finding"] = "Evidence is too dark to judge."
        result = self.record_round(
            state_path, report, render_args, comparison_args, expected=2
        )
        self.assertIn("Hard gates override", result.stderr)

    def test_continue_rejects_unjudgeable_or_not_applicable_evidence(self) -> None:
        state_path, spec_path = self.initialize("simple")
        self.admit_intake(state_path, spec_path)
        render_args, comparison_args, views = self.evidence()
        report = self.critic_report(
            "critic-fail-closed", "context-fail-closed", "continue", 0.95, None, "none", views
        )
        report["viewEvidence"][0]["judgeable"] = False
        report["evidenceSufficiency"]["sufficient"] = True
        result = self.record_round(
            state_path, report, render_args, comparison_args, expected=2
        )
        self.assertIn("positively judgeable", result.stderr)

        report["viewEvidence"][0]["judgeable"] = True
        report["universalChecklist"][0]["status"] = "not-applicable"
        result = self.record_round(
            state_path, report, render_args, comparison_args, expected=2
        )
        self.assertIn("pass positively", result.stderr)

    def test_forensic_critic_is_advisory_not_an_approval_substitute(self) -> None:
        state_path, spec_path = self.initialize("simple")
        self.admit_intake(state_path, spec_path)
        render_args, comparison_args, views = self.evidence()
        report = self.critic_report(
            "forensic-only", "context-forensic", "continue", 0.95, None, "none", views
        )
        report["critic"]["role"] = "forensic-subject-matter-critic"
        result = self.record_round(
            state_path, report, render_args, comparison_args, expected=2
        )
        self.assertIn("advisory", result.stderr)

    def test_contract_added_view_is_enforced_at_runtime(self) -> None:
        state_path, spec_path = self.initialize("simple")
        spec = json.loads(spec_path.read_text(encoding="utf-8"))
        spec["qualityContract"]["requiredViews"].append("underside")
        write_json(spec_path, spec)
        self.run_cli("validate", state_path)
        self.admit_intake(state_path, spec_path)
        render_args, comparison_args, views = self.evidence()
        report = self.critic_report(
            "critic-custom-view", "context-custom-view", "continue", 0.95, None, "none", views
        )
        result = self.record_round(
            state_path, report, render_args, comparison_args, expected=2
        )
        self.assertIn("Missing required render evidence role: underside", result.stderr)

    def test_approved_contract_mutation_blocks_visual_pass_opening(self) -> None:
        state_path, spec_path = self.initialize("simple")
        self.admit_intake(state_path, spec_path)
        spec = json.loads(spec_path.read_text(encoding="utf-8"))
        spec["subjectRoutes"] = []
        spec["qualityContract"]["globalThreshold"] = 0.1
        write_json(spec_path, spec)
        start_checkpoint = self.root / "mutated-start.blend"
        start_checkpoint.write_bytes(b"start")
        start_render = self.root / "mutated-start.png"
        start_render.write_bytes(b"start-render")
        result = self.run_cli(
            "open-pass",
            state_path,
            "--pass-id",
            "camera-match",
            "--builder-id",
            "builder-camera",
            "--start-checkpoint",
            start_checkpoint,
            "--start-reference-render",
            start_render,
            expected=2,
        )
        self.assertIn("changed after approval", result.stderr)

    def test_checklist_evidence_roles_must_resolve_to_admitted_files(self) -> None:
        state_path, spec_path = self.initialize("simple")
        self.admit_intake(state_path, spec_path)
        render_args, comparison_args, views = self.evidence()
        report = self.critic_report(
            "critic-citation", "context-citation", "continue", 0.95, None, "none", views
        )
        report["universalChecklist"][0]["evidenceRoles"] = ["invented-view"]
        result = self.record_round(
            state_path, report, render_args, comparison_args, expected=2
        )
        self.assertIn("cites unadmitted roles", result.stderr)

    def test_missing_deterministic_role_is_rejected(self) -> None:
        state_path, spec_path = self.initialize("simple")
        self.admit_intake(state_path, spec_path)
        render_args, comparison_args, views = self.evidence()
        filtered_args: list[str] = []
        for index in range(0, len(render_args), 2):
            if not render_args[index + 1].startswith("grazing-light="):
                filtered_args.extend(render_args[index : index + 2])
        report = self.critic_report(
            "critic-evidence", "context-evidence", "continue", 0.9, None, "none", views
        )
        report["viewEvidence"] = [
            view for view in report["viewEvidence"] if view["role"] != "grazing-light"
        ]
        result = self.record_round(
            state_path, report, filtered_args, comparison_args, expected=2
        )
        self.assertIn("Missing required render evidence role: grazing-light", result.stderr)

    def test_feature_contract_must_cover_observations_exactly_once(self) -> None:
        state_path, spec_path = self.initialize("simple")
        spec = json.loads(spec_path.read_text(encoding="utf-8"))
        spec["featureContract"].pop()
        write_json(spec_path, spec)
        result = self.run_cli("validate", state_path, expected=1)
        self.assertIn("map every observed feature exactly once", result.stdout)

    def test_two_small_deltas_force_plateau_exit(self) -> None:
        state_path, spec_path = self.initialize("complex")
        self.admit_intake(state_path, spec_path)
        render_args, comparison_args, views = self.evidence()

        first = self.critic_report(
            "critic-p1", "context-p1", "refine-scene", 0.8, None, "root-1", views
        )
        self.record_round(state_path, first, render_args, comparison_args)
        self.correct(state_path, "root-1")

        second = self.critic_report(
            "critic-p2", "context-p2", "refine-scene", 0.81, 0.01, "root-2", views
        )
        self.record_round(state_path, second, render_args, comparison_args)
        self.correct(state_path, "root-2")

        third = self.critic_report(
            "critic-p3", "context-p3", "refine-scene", 0.815, 0.005, "root-3", views
        )
        result = self.record_round(
            state_path, third, render_args, comparison_args, expected=2
        )
        self.assertIn("constitute a plateau", result.stderr)

    def test_refine_spec_uses_typed_validated_revision_not_blend_correction(self) -> None:
        state_path, spec_path = self.initialize("simple")
        self.admit_intake(state_path, spec_path)
        render_args, comparison_args, views = self.evidence()
        report = self.critic_report(
            "critic-spec", "context-spec", "refine-spec", 0.8, None, "spec-root", views
        )
        self.record_round(state_path, report, render_args, comparison_args)
        checkpoint = self.root / "wrong-correction.blend"
        checkpoint.write_bytes(b"wrong")
        wrong = self.run_cli(
            "correct",
            state_path,
            "--pass-id",
            "camera-match",
            "--builder-id",
            "builder-camera",
            "--root-cause-id",
            "spec-root",
            "--summary",
            "Wrong transition type.",
            "--changed",
            "body.scale",
            "--checkpoint",
            checkpoint,
            expected=2,
        )
        self.assertIn("awaiting-correction", wrong.stderr)

        spec = json.loads(spec_path.read_text(encoding="utf-8"))
        spec["qualityContract"]["definitionOfDone"].append(
            "Revised camera evidence statement."
        )
        write_json(spec_path, spec)
        self.run_cli(
            "revise-spec",
            state_path,
            "--pass-id",
            "camera-match",
            "--builder-id",
            "builder-camera",
            "--root-cause-id",
            "spec-root",
            "--summary",
            "Added the missing camera evidence condition.",
            "--spec",
            spec_path,
        )
        state = json.loads(state_path.read_text(encoding="utf-8"))
        self.assertEqual(state["status"], "active")
        self.assertEqual(state["passes"][1]["corrections"][-1]["type"], "spec-revision")

    def test_schema_v1_migration_creates_backups_and_manual_markers(self) -> None:
        project = self.root / "legacy"
        project.mkdir()
        reference = project / "legacy-reference.png"
        reference.write_bytes(b"legacy")
        spec_path = project / "reconstruction-spec.json"
        state_path = project / "reconstruction-state.json"
        spec_text = (FIXTURES / "legacy-spec-v1.json").read_text(encoding="utf-8")
        spec_text = spec_text.replace("__REFERENCE_PATH__", str(reference))
        spec_path.write_text(spec_text, encoding="utf-8")
        state_text = (FIXTURES / "legacy-state-v1.json").read_text(encoding="utf-8")
        state_text = state_text.replace("__PROJECT_DIR__", str(project))
        state_text = state_text.replace("__SPEC_PATH__", str(spec_path))
        state_path.write_text(state_text, encoding="utf-8")

        self.run_cli("migrate", state_path)
        migrated_state = json.loads(state_path.read_text(encoding="utf-8"))
        migrated_spec = json.loads(spec_path.read_text(encoding="utf-8"))
        self.assertEqual(migrated_state["schemaVersion"], 2)
        self.assertEqual(migrated_spec["schemaVersion"], 2)
        self.assertTrue(state_path.with_suffix(".v1.json").is_file())
        self.assertTrue(spec_path.with_suffix(".v1.json").is_file())
        self.assertTrue(migrated_spec["migrationNotes"])
        self.assertEqual(
            [item["id"] for item in migrated_state["passes"]],
            [item["id"] for item in pipeline.PASS_DEFS],
        )

    def test_fabricated_zero_error_audit_is_rejected(self) -> None:
        checkpoint = self.root / "audited.blend"
        checkpoint.write_bytes(b"checkpoint")
        audit_path = self.root / "fake-audit.json"
        write_json(audit_path, {"summary": {"errors": 0}})
        with self.assertRaisesRegex(ValueError, "schemaVersion"):
            pipeline.validate_audit(
                audit_path,
                "final",
                {
                    "path": str(checkpoint.resolve()),
                    "sha256": file_hash(checkpoint),
                },
                {"reference-match": "render"},
            )

    def test_final_permitted_round_cannot_deadlock_on_refinement(self) -> None:
        state_path, spec_path = self.initialize("complex")
        state = json.loads(state_path.read_text(encoding="utf-8"))
        state["criticPolicy"]["maximumRoundsPerPass"] = 2
        write_json(state_path, state)
        self.admit_intake(state_path, spec_path)
        render_args, comparison_args, views = self.evidence()
        first = self.critic_report(
            "critic-cap-1", "context-cap-1", "refine-scene", 0.8, None, "cap-root-1", views
        )
        self.record_round(state_path, first, render_args, comparison_args)
        self.correct(state_path, "cap-root-1")
        second = self.critic_report(
            "critic-cap-2", "context-cap-2", "refine-scene", 0.84, 0.04, "cap-root-2", views
        )
        result = self.record_round(
            state_path, second, render_args, comparison_args, expected=2
        )
        self.assertIn("final permitted critic round", result.stderr)

        second["decision"] = "request-input"
        result = self.record_round(
            state_path, second, render_args, comparison_args, expected=2
        )
        self.assertIn("input cycle", result.stderr)


class ComparisonAutomationTests(unittest.TestCase):
    def test_comparison_outputs_are_deterministic_and_dimension_checked(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            reference = root / "reference.png"
            current = root / "current.png"
            previous = root / "previous.png"
            Image.new("RGB", (32, 24), (10, 20, 30)).save(reference)
            Image.new("RGB", (32, 24), (15, 25, 35)).save(current)
            Image.new("RGB", (32, 24), (5, 15, 25)).save(previous)
            output = root / "out"
            command = [
                sys.executable,
                str(COMPARISONS),
                "--reference",
                str(reference),
                "--current",
                str(current),
                "--previous",
                str(previous),
                "--out-dir",
                str(output),
            ]
            first = subprocess.run(command, text=True, capture_output=True, check=False)
            self.assertEqual(first.returncode, 0, first.stderr)
            overlay = output / "reference-overlay.png"
            first_hash = hashlib.sha256(overlay.read_bytes()).hexdigest()
            second = subprocess.run(command, text=True, capture_output=True, check=False)
            self.assertEqual(second.returncode, 0, second.stderr)
            self.assertEqual(first_hash, hashlib.sha256(overlay.read_bytes()).hexdigest())

            Image.new("RGB", (16, 16), (0, 0, 0)).save(previous)
            mismatch = subprocess.run(command, text=True, capture_output=True, check=False)
            self.assertEqual(mismatch.returncode, 2)
            self.assertIn("must share exact dimensions", mismatch.stdout)


class BlenderIntegrationTests(unittest.TestCase):
    def test_final_audit_rejects_ignored_mesh_and_accepts_reference_match_role(self) -> None:
        blender = shutil.which("blender")
        if blender is None:
            app_binary = Path("/Applications/Blender.app/Contents/MacOS/Blender")
            blender = str(app_binary) if app_binary.is_file() else None
        if blender is None:
            self.skipTest("Blender executable is unavailable")
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            blend = root / "probe.blend"
            report = root / "audit.json"
            create = subprocess.run(
                [
                    blender,
                    "--background",
                    "--python",
                    str(Path(__file__).parent / "blender_fixture_scene.py"),
                    "--",
                    str(blend),
                ],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(create.returncode, 0, create.stderr)
            audit = subprocess.run(
                [
                    blender,
                    "--background",
                    str(blend),
                    "--python",
                    str(SKILL_ROOT / "scripts" / "blender_scene_audit.py"),
                    "--",
                    "--out",
                    str(report),
                    "--stage",
                    "final",
                    "--strict",
                    "--allow-realtime",
                    "--required-role",
                    "reference-match",
                    "--required-role",
                    "orbit-left",
                    "--required-role",
                    "orbit-right",
                ],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(audit.returncode, 1, audit.stdout + audit.stderr)
            payload = json.loads(report.read_text(encoding="utf-8"))
            codes = {item["code"] for item in payload["issues"]}
            self.assertIn("audit-ignore-forbidden-in-scope", codes)
            self.assertNotIn("missing-reference-camera", codes)


if __name__ == "__main__":
    unittest.main()
