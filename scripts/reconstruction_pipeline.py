#!/usr/bin/env python3
"""Deterministic state, evidence, and independent-review controller for img2blender."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import sys
import tempfile
import uuid
from pathlib import Path
from typing import Any

from contract_options import (
    TASK_MODES,
    VALIDATION_SCOPES,
    inspection_roles,
    validate_inspection_evidence,
    validate_options,
)
from geometry_invariants import (
    applicable_invariants,
    validate_invariant_report,
    validate_invariants,
)

SCHEMA_VERSION = 2
LEGACY_SCHEMA_VERSION = 1

TOPOLOGY_CLASSES = {
    "continuous-sculpt",
    "assembled-solid",
    "conforming-shell",
    "surface-relief",
    "fiber-strand",
    "material-only",
}
IMPLEMENTATION_KINDS = {
    "geometry",
    "material-mask",
    "decal",
    "node-system",
    "displacement",
    "texture",
    "deferred",
}
SUITABILITY_VALUES = {"pass", "conditional", "request-input", "reject"}
DETAIL_MINIMUMS = {"simple": 3, "moderate": 6, "complex": 10, "ultra": 16}
SUBJECT_ROUTES = {
    "architecture-environment",
    "product-vehicle",
    "hard-surface-prop",
    "organic-creature",
    "human-character",
    "cloth-hair",
    "botanical",
    "transparent-translucent",
    "generated-scanned-import",
}

UNIVERSAL_CHECKS = (
    "camera-framing",
    "silhouette-proportion",
    "depth-cross-section",
    "structural-attachment-contact",
    "topology-shading",
    "material-physicality-tiling",
    "lighting-color",
    "scale-cues",
    "environment-grounding",
    "narrative-detail-density",
    "presentation",
    "delivery-integrity",
)

SUBJECT_CHECKS = {
    "architecture-environment": (
        "composition-layout-fidelity",
        "mass-hierarchy",
        "circulation-access",
        "facade-detail-visible-elevations",
        "roof-drainage-support-logic",
        "windows-interiors",
        "terrain-integration",
        "population-activities-props-signage",
        "repetition-control",
        "wide-scene-atmospheric-depth",
    ),
    "product-vehicle": (
        "stance-contact-points",
        "panel-flow-gaps-shut-lines",
        "functional-assembly-clearance",
        "glass-trim-seals",
        "underside-rear-volume",
        "reflection-continuity",
    ),
    "hard-surface-prop": (
        "construction-axes",
        "part-boundaries-thickness",
        "fastener-clearance-logic",
        "profile-cross-sections",
        "bevel-edge-hierarchy",
        "reflection-flow",
    ),
    "organic-creature": (
        "gesture-primary-masses",
        "skeletal-landmarks",
        "anatomical-attachment-transitions",
        "section-thickness",
        "asymmetry-specificity",
        "frequency-layering",
    ),
    "human-character": (
        "likeness-landmarks",
        "head-body-proportions",
        "pose-joint-angles",
        "eyes-mouth-skin-depth",
        "hair-costume-silhouette",
        "deformation-topology",
    ),
    "cloth-hair": (
        "construction-layer-order",
        "tension-compression-gravity",
        "silhouette-masses-flow",
        "seams-hems-piping",
        "clump-strand-rhythm",
        "body-contact-clearance",
    ),
    "botanical": (
        "branching-hierarchy",
        "density-gradients-gaps",
        "phyllotaxis-distribution",
        "scale-orientation-variation",
        "gravity-wind-light-response",
        "damage-color-locality",
    ),
    "transparent-translucent": (
        "physical-thickness",
        "ior-transmission-separation",
        "absorption-scattering",
        "reflection-refraction-environment",
        "internal-form-legibility",
        "caustic-emission-justification",
    ),
    "generated-scanned-import": (
        "source-provenance-license",
        "original-import-preserved",
        "floaters-fusions-cleaned",
        "baked-illusion-rebuilt",
        "identity-components-reconstructed",
        "retopo-uv-independent-channels",
    ),
}

BASE_VIEW_ROLES = {
    "reference-match": "render",
    "reference-overlay": "comparison",
    "clay-silhouette": "render",
    "orbit-left": "render",
    "orbit-right": "render",
    "neutral-material": "render",
    "grazing-light": "render",
    "previous-iteration": "comparison",
}
ARCHITECTURE_VIEW_ROLES = {
    "back": "render",
    "ortho-front": "render",
    "ortho-left": "render",
    "ortho-right": "render",
    "ortho-back": "render",
    "ortho-top": "render",
}

MANDATORY_HARD_GATES = (
    "evidence-judgeable",
    "reference-camera-locked",
    "generic-resemblance-only",
    "critical-features-visible-supported",
    "attachments-contact",
    "floating-intersecting-geometry",
    "multi-view-consistency",
    "delivery-integrity",
)

PASS_DEFS = [
    {"id": "intake", "label": "Reference analysis and reconstruction contract", "auditStage": None},
    {"id": "camera-match", "label": "Reference camera match", "auditStage": None},
    {"id": "blockout", "label": "Silhouette, proportions, and depth blockout", "auditStage": None},
    {"id": "primary-form", "label": "Primary form and cross-sections", "auditStage": None},
    {"id": "secondary-form", "label": "Secondary form and assembly", "auditStage": None},
    {"id": "topology-uv", "label": "Topology, normals, and UVs", "auditStage": "working"},
    {"id": "materials", "label": "Materials and surface response", "auditStage": None},
    {"id": "lighting", "label": "Lighting, color management, and reference match", "auditStage": None},
    {"id": "microdetail", "label": "Identity-bearing microdetail", "auditStage": None},
    {"id": "final-delivery", "label": "Final multi-view and delivery validation", "auditStage": "final"},
]
PASS_IDS = {item["id"] for item in PASS_DEFS}

ACTIONS = {
    "continue",
    "refine-spec",
    "refine-scene",
    "refine-camera-light",
    "request-input",
    "stop",
}
REFINEMENT_ACTIONS = {"refine-spec", "refine-scene", "refine-camera-light"}
PLATEAU_EXIT_ACTIONS = {"refine-spec", "request-input", "stop"}


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


def read_json(path: Path) -> dict[str, Any]:
    try:
        with path.open("r", encoding="utf-8") as handle:
            value = json.load(handle)
    except FileNotFoundError as exc:
        raise ValueError(f"File does not exist: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON in {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"Expected a JSON object in {path}")
    return value


def atomic_write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temp_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent)
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(value, handle, indent=2, ensure_ascii=False)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, path)
    finally:
        if os.path.exists(temp_name):
            os.unlink(temp_name)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_hash(value: Any) -> str:
    encoded = json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def append_transition(
    state: dict[str, Any], event_type: str, payload: dict[str, Any]
) -> None:
    ledger = state.setdefault("transitionLedger", [])
    previous_hash = ledger[-1]["eventHash"] if ledger else None
    event = {
        "sequence": len(ledger) + 1,
        "timestamp": utc_now(),
        "type": event_type,
        "payload": payload,
        "previousHash": previous_hash,
    }
    event["eventHash"] = canonical_hash(event)
    ledger.append(event)


def verify_transition_ledger(state: dict[str, Any]) -> None:
    ledger = state.get("transitionLedger")
    if not isinstance(ledger, list) or not ledger:
        raise ValueError("State lacks the schema-v2 transition ledger")
    previous_hash = None
    for index, event in enumerate(ledger):
        if not isinstance(event, dict):
            raise ValueError(f"Transition ledger event {index + 1} is not an object")
        supplied_hash = event.get("eventHash")
        unsigned = {key: value for key, value in event.items() if key != "eventHash"}
        if event.get("sequence") != index + 1:
            raise ValueError("Transition ledger sequence is invalid")
        if event.get("previousHash") != previous_hash:
            raise ValueError("Transition ledger hash chain is broken")
        if supplied_hash != canonical_hash(unsigned):
            raise ValueError("Transition ledger event hash is invalid")
        previous_hash = supplied_hash


def evidence_record(path_text: str, role: str | None = None, kind: str | None = None) -> dict[str, Any]:
    path = Path(path_text).expanduser().resolve()
    if not path.is_file():
        raise ValueError(f"Evidence file does not exist: {path}")
    record: dict[str, Any] = {
        "path": str(path),
        "sha256": sha256_file(path),
        "bytes": path.stat().st_size,
    }
    if role is not None:
        record["role"] = role
    if kind is not None:
        record["kind"] = kind
    return record


def canonical_role(value: str) -> str:
    """Return the single case-insensitive representation used for evidence roles."""
    return value.strip().lower()


def critical_closeup_role(feature_id: Any) -> str:
    """Map a case-sensitive feature ID to its canonical evidence-role suffix."""
    return f"critical-closeup:{canonical_role(str(feature_id))}"


def parse_role_evidence(values: list[str], kind: str) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    seen: set[str] = set()
    for value in values:
        if "=" not in value:
            raise ValueError(
                f"{kind} evidence must use ROLE=/absolute/path syntax; got {value!r}"
            )
        role, path_text = value.split("=", 1)
        role = canonical_role(role)
        if not role or not path_text.strip():
            raise ValueError(f"Invalid {kind} evidence mapping: {value!r}")
        if role in seen:
            raise ValueError(f"Duplicate {kind} evidence role: {role}")
        seen.add(role)
        records.append(evidence_record(path_text, role=role, kind=kind))
    return records


def require_nonempty_list(
    value: Any, field: str, errors: list[str], minimum: int = 1
) -> list[Any]:
    if not isinstance(value, list) or len(value) < minimum:
        errors.append(f"{field} must contain at least {minimum} item(s)")
        return []
    return value


def require_string(value: Any, field: str, errors: list[str]) -> str:
    if not isinstance(value, str) or not value.strip():
        errors.append(f"{field} must be a non-empty string")
        return ""
    return value.strip()


def require_bool(value: Any, field: str, errors: list[str]) -> None:
    if not isinstance(value, bool):
        errors.append(f"{field} must be a boolean")


def require_confidence(value: Any, field: str, errors: list[str]) -> None:
    if (
        not isinstance(value, (int, float))
        or isinstance(value, bool)
        or not 0 <= value <= 1
    ):
        errors.append(f"{field} must be a number from 0 to 1")


def score_number(value: Any, field: str) -> float:
    if (
        not isinstance(value, (int, float))
        or isinstance(value, bool)
        or not 0 <= value <= 1
    ):
        raise ValueError(f"{field} must be a number from 0 to 1")
    return float(value)


def pass_definition(pass_id: str) -> dict[str, Any]:
    for definition in PASS_DEFS:
        if definition["id"] == pass_id:
            return definition
    raise ValueError(f"Unknown pass id: {pass_id}")


def pass_state(state: dict[str, Any], pass_id: str) -> dict[str, Any]:
    for record in state.get("passes", []):
        if record.get("id") == pass_id:
            return record
    raise ValueError(f"Pass missing from state: {pass_id}")


def min_critic_rounds(complexity: str) -> int:
    return 2 if complexity in {"complex", "ultra"} else 1


def required_view_roles(spec: dict[str, Any], pass_id: str) -> dict[str, str]:
    if pass_id == "intake":
        return {}
    roles = dict(BASE_VIEW_ROLES)
    roles.update(inspection_roles(spec))
    if spec.get("refinementScope"):
        roles["integration-context"] = "render"
    routes = set(spec.get("subjectRoutes", []))
    contract = spec.get("qualityContract", {})
    for role in contract.get("requiredViews", []):
        normalized = canonical_role(str(role))
        if normalized:
            roles[normalized] = (
                "comparison"
                if normalized in {"reference-overlay", "previous-iteration"}
                else "render"
            )
    if "architecture-environment" in routes:
        roles.update(ARCHITECTURE_VIEW_ROLES)
    elif contract.get("backReviewRequired") is True:
        roles["back"] = "render"
    for feature in critical_for_pass(contract, pass_id):
        roles[critical_closeup_role(feature["id"])] = "render"
    return roles


def critical_for_pass(contract: dict[str, Any], pass_id: str) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    for feature in contract.get("criticalFeatures", []):
        if not isinstance(feature, dict):
            continue
        assigned = feature.get("passes")
        if not assigned or pass_id in assigned:
            selected.append(feature)
    return selected


def load_state(path_text: str, allow_legacy: bool = False) -> tuple[Path, dict[str, Any]]:
    path = Path(path_text).expanduser().resolve()
    state = read_json(path)
    version = state.get("schemaVersion")
    if version == LEGACY_SCHEMA_VERSION and not allow_legacy:
        raise ValueError(
            "This is an img2blender schema v1 state. Run the migrate command before use."
        )
    if version not in ({SCHEMA_VERSION, LEGACY_SCHEMA_VERSION} if allow_legacy else {SCHEMA_VERSION}):
        raise ValueError(
            f"Unsupported state schemaVersion {version}; expected {SCHEMA_VERSION}"
        )
    if version == SCHEMA_VERSION:
        verify_transition_ledger(state)
    return path, state


def ensure_pinned_contract(state: dict[str, Any]) -> dict[str, Any]:
    pin = state.get("approvedContract")
    if not isinstance(pin, dict):
        raise ValueError("No approved reconstruction contract is pinned")
    spec_path = Path(state["specPath"])
    if sha256_file(spec_path) != pin.get("sha256"):
        raise ValueError(
            "The reconstruction contract changed after approval; "
            "use a typed refine-spec/revise-spec transition"
        )
    errors, _ = validate_spec(state)
    if errors:
        raise ValueError("Pinned reconstruction contract no longer validates:\n- " + "\n- ".join(errors))
    spec = read_json(spec_path)
    current_reference_hashes = {
        record.get("id"): record.get("sha256")
        for record in spec.get("references", [])
        if isinstance(record, dict)
    }
    if current_reference_hashes != pin.get("referenceHashes"):
        raise ValueError("Pinned reference hashes changed after intake")
    return spec


def validate_spec(state: dict[str, Any]) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    spec_path = Path(state.get("specPath", ""))
    try:
        spec = read_json(spec_path)
    except ValueError as exc:
        return [str(exc)], warnings

    if spec.get("schemaVersion") != SCHEMA_VERSION:
        errors.append(f"schemaVersion must be {SCHEMA_VERSION}")

    errors.extend(validate_options(spec))
    errors.extend(validate_invariants(spec))

    references = require_nonempty_list(spec.get("references"), "references", errors)
    reference_ids: set[str] = set()
    for index, record in enumerate(references):
        prefix = f"references[{index}]"
        if not isinstance(record, dict):
            errors.append(f"{prefix} must be an object")
            continue
        reference_id = require_string(record.get("id"), f"{prefix}.id", errors)
        if reference_id in reference_ids:
            errors.append(f"Duplicate reference id: {reference_id}")
        reference_ids.add(reference_id)
        ref_path = Path(str(record.get("path", "")))
        if not ref_path.is_file():
            errors.append(f"{prefix}.path does not exist: {ref_path}")
            continue
        expected_hash = record.get("sha256")
        if not isinstance(expected_hash, str) or len(expected_hash) != 64:
            errors.append(f"{prefix}.sha256 must be a complete SHA-256 digest")
        elif sha256_file(ref_path) != expected_hash:
            errors.append(f"{prefix} changed since intake; re-admit it and update its hash")
        require_string(record.get("role"), f"{prefix}.role", errors)

    routes = require_nonempty_list(spec.get("subjectRoutes"), "subjectRoutes", errors)
    unknown_routes = sorted({str(item) for item in routes} - SUBJECT_ROUTES)
    if unknown_routes:
        errors.append(f"subjectRoutes contains unknown routes: {unknown_routes}")

    analysis = spec.get("referenceAnalysis")
    if not isinstance(analysis, dict):
        errors.append("referenceAnalysis must be an object")
        analysis = {}
    suitability = analysis.get("suitability")
    if suitability not in SUITABILITY_VALUES:
        errors.append(
            "referenceAnalysis.suitability must be pass, conditional, request-input, or reject"
        )
    elif suitability in {"request-input", "reject"}:
        errors.append(f"referenceAnalysis.suitability is {suitability}; intake cannot continue")

    classification = analysis.get("classification")
    if not isinstance(classification, dict):
        errors.append("referenceAnalysis.classification must be an object")
    else:
        require_string(
            classification.get("primaryType"),
            "referenceAnalysis.classification.primaryType",
            errors,
        )
        require_string(
            classification.get("domain"),
            "referenceAnalysis.classification.domain",
            errors,
        )
        require_confidence(
            classification.get("confidence"),
            "referenceAnalysis.classification.confidence",
            errors,
        )
    require_nonempty_list(
        analysis.get("observations"), "referenceAnalysis.observations", errors, minimum=4
    )
    observed_features = require_nonempty_list(
        analysis.get("observedFeatures"),
        "referenceAnalysis.observedFeatures",
        errors,
        minimum=DETAIL_MINIMUMS.get(state.get("complexity"), 6),
    )
    observed_ids: set[str] = set()
    for index, feature in enumerate(observed_features):
        prefix = f"referenceAnalysis.observedFeatures[{index}]"
        if not isinstance(feature, dict):
            errors.append(f"{prefix} must be an object")
            continue
        feature_id = require_string(feature.get("id"), f"{prefix}.id", errors)
        if feature_id in observed_ids:
            errors.append(f"Duplicate observed feature id: {feature_id}")
        observed_ids.add(feature_id)
        require_string(feature.get("particular"), f"{prefix}.particular", errors)
        evidence_refs = require_nonempty_list(
            feature.get("evidenceRefs"), f"{prefix}.evidenceRefs", errors
        )
        for ref in evidence_refs:
            if ref not in reference_ids:
                errors.append(f"{prefix}.evidenceRefs contains unknown reference: {ref}")
        require_confidence(feature.get("confidence"), f"{prefix}.confidence", errors)
    if not isinstance(analysis.get("inferences"), list):
        errors.append("referenceAnalysis.inferences must be a list")
    if not isinstance(analysis.get("cameraEvidence"), dict):
        errors.append("referenceAnalysis.cameraEvidence must be an object")
    if not isinstance(analysis.get("scaleEvidence"), dict):
        errors.append("referenceAnalysis.scaleEvidence must be an object")
    if not isinstance(analysis.get("contradictions"), list):
        errors.append("referenceAnalysis.contradictions must be a list")

    components = require_nonempty_list(spec.get("componentPlan"), "componentPlan", errors)
    component_ids: set[str] = set()
    for index, component in enumerate(components):
        prefix = f"componentPlan[{index}]"
        if not isinstance(component, dict):
            errors.append(f"{prefix} must be an object")
            continue
        component_id = require_string(component.get("id"), f"{prefix}.id", errors)
        if component_id in component_ids:
            errors.append(f"Duplicate component id: {component_id}")
        component_ids.add(component_id)
        require_string(component.get("name"), f"{prefix}.name", errors)
        if component.get("topologyClass") not in TOPOLOGY_CLASSES:
            errors.append(f"{prefix}.topologyClass must be one of {sorted(TOPOLOGY_CLASSES)}")
        require_string(component.get("modelingRoute"), f"{prefix}.modelingRoute", errors)
        component_refs = require_nonempty_list(
            component.get("evidenceRefs"), f"{prefix}.evidenceRefs", errors
        )
        for ref in component_refs:
            if ref not in reference_ids:
                errors.append(f"{prefix}.evidenceRefs contains unknown reference: {ref}")
        require_confidence(component.get("confidence"), f"{prefix}.confidence", errors)
    for index, component in enumerate(components):
        if isinstance(component, dict):
            parent = component.get("parentId")
            if parent and parent not in component_ids:
                errors.append(f"componentPlan[{index}].parentId refers to unknown component: {parent}")

    materials = require_nonempty_list(spec.get("materialPlan"), "materialPlan", errors)
    material_ids: set[str] = set()
    for index, material in enumerate(materials):
        prefix = f"materialPlan[{index}]"
        if not isinstance(material, dict):
            errors.append(f"{prefix} must be an object")
            continue
        material_id = require_string(material.get("id"), f"{prefix}.id", errors)
        if material_id in material_ids:
            errors.append(f"Duplicate material id: {material_id}")
        material_ids.add(material_id)
        assigned_components = require_nonempty_list(
            material.get("componentIds"), f"{prefix}.componentIds", errors
        )
        for component_id in assigned_components:
            if component_id not in component_ids:
                errors.append(f"{prefix}.componentIds contains unknown component: {component_id}")
        channels = material.get("channels")
        if not isinstance(channels, dict):
            errors.append(f"{prefix}.channels must be an object")
        else:
            for channel in ("baseColor", "roughness", "normalOrHeight"):
                require_string(channels.get(channel), f"{prefix}.channels.{channel}", errors)
        material_refs = require_nonempty_list(
            material.get("evidenceRefs"), f"{prefix}.evidenceRefs", errors
        )
        for ref in material_refs:
            if ref not in reference_ids:
                errors.append(f"{prefix}.evidenceRefs contains unknown reference: {ref}")
        require_confidence(material.get("confidence"), f"{prefix}.confidence", errors)

    feature_contract = require_nonempty_list(
        spec.get("featureContract"),
        "featureContract",
        errors,
        minimum=len(observed_ids) or 1,
    )
    mapped_ids: list[str] = []
    all_subject_checks = {
        check for route in routes if route in SUBJECT_CHECKS for check in SUBJECT_CHECKS[route]
    }
    for index, mapping in enumerate(feature_contract):
        prefix = f"featureContract[{index}]"
        if not isinstance(mapping, dict):
            errors.append(f"{prefix} must be an object")
            continue
        feature_id = require_string(mapping.get("featureId"), f"{prefix}.featureId", errors)
        mapped_ids.append(feature_id)
        require_string(mapping.get("observedParticular"), f"{prefix}.observedParticular", errors)
        implementation = mapping.get("implementation")
        if not isinstance(implementation, dict):
            errors.append(f"{prefix}.implementation must be an object")
        else:
            if implementation.get("kind") not in IMPLEMENTATION_KINDS:
                errors.append(
                    f"{prefix}.implementation.kind must be one of {sorted(IMPLEMENTATION_KINDS)}"
                )
            require_string(implementation.get("target"), f"{prefix}.implementation.target", errors)
        checklist_items = require_nonempty_list(
            mapping.get("subjectChecklistItems"),
            f"{prefix}.subjectChecklistItems",
            errors,
        )
        for item in checklist_items:
            if item not in all_subject_checks:
                errors.append(f"{prefix}.subjectChecklistItems contains unknown item: {item}")
        review_cameras = require_nonempty_list(
            mapping.get("reviewCameras"), f"{prefix}.reviewCameras", errors
        )
        expected_critical_role = critical_closeup_role(feature_id)
        if mapping.get("critical") is True and expected_critical_role not in {
            canonical_role(str(camera)) for camera in review_cameras
        }:
            errors.append(
                f"{prefix}.reviewCameras must include {expected_critical_role} "
                "for a critical feature"
            )
        evidence_refs = require_nonempty_list(
            mapping.get("evidenceRefs"), f"{prefix}.evidenceRefs", errors
        )
        for ref in evidence_refs:
            if ref not in reference_ids:
                errors.append(f"{prefix}.evidenceRefs contains unknown reference: {ref}")
        require_confidence(mapping.get("confidence"), f"{prefix}.confidence", errors)
        observed_match = next(
            (
                item
                for item in observed_features
                if isinstance(item, dict) and item.get("id") == feature_id
            ),
            None,
        )
        if observed_match and mapping.get("observedParticular") != observed_match.get("particular"):
            errors.append(
                f"{prefix}.observedParticular must exactly match the observed feature particular"
            )

    if set(mapped_ids) != observed_ids or len(mapped_ids) != len(set(mapped_ids)):
        missing = sorted(observed_ids - set(mapped_ids))
        extra = sorted(set(mapped_ids) - observed_ids)
        duplicates = sorted({item for item in mapped_ids if mapped_ids.count(item) > 1})
        errors.append(
            "featureContract must map every observed feature exactly once; "
            f"missing={missing}, extra={extra}, duplicates={duplicates}"
        )

    inventory = spec.get("detailInventory")
    if not isinstance(inventory, dict):
        errors.append("detailInventory must be an object")
        inventory = {}
    minimum = inventory.get("minimum")
    if not isinstance(minimum, int) or minimum < 0:
        errors.append("detailInventory.minimum must be a non-negative integer")
        minimum = DETAIL_MINIMUMS.get(state.get("complexity"), 6)
    items = inventory.get("items")
    if not isinstance(items, list):
        errors.append("detailInventory.items must be a list")
        items = []
    if len(items) < minimum:
        errors.append(f"detailInventory.items has {len(items)} entries; minimum is {minimum}")
    detail_ids: set[str] = set()
    for index, item in enumerate(items):
        prefix = f"detailInventory.items[{index}]"
        if not isinstance(item, dict):
            errors.append(f"{prefix} must be an object")
            continue
        detail_id = require_string(item.get("id"), f"{prefix}.id", errors)
        if detail_id in detail_ids:
            errors.append(f"Duplicate detail inventory id: {detail_id}")
        detail_ids.add(detail_id)
        for field in ("kind", "region", "affects", "evidenceRef", "mapsTo"):
            require_string(item.get(field), f"{prefix}.{field}", errors)
        if item.get("evidenceRef") not in reference_ids:
            errors.append(f"{prefix}.evidenceRef contains unknown reference")
        require_confidence(item.get("confidence"), f"{prefix}.confidence", errors)

    unknowns = spec.get("unknowns")
    if not isinstance(unknowns, list):
        errors.append("unknowns must be a list")
        unknowns = []
    for index, unknown in enumerate(unknowns):
        prefix = f"unknowns[{index}]"
        if not isinstance(unknown, dict):
            errors.append(f"{prefix} must be an object")
            continue
        for key in ("region", "impact", "disposition"):
            require_string(unknown.get(key), f"{prefix}.{key}", errors)
        require_confidence(unknown.get("confidence"), f"{prefix}.confidence", errors)

    contract = spec.get("qualityContract")
    if not isinstance(contract, dict):
        errors.append("qualityContract must be an object")
        contract = {}
    require_nonempty_list(contract.get("definitionOfDone"), "qualityContract.definitionOfDone", errors)
    critical_features = require_nonempty_list(
        contract.get("criticalFeatures"), "qualityContract.criticalFeatures", errors
    )
    contract_feature_ids: set[str] = set()
    contract_critical_roles: set[str] = set()
    for index, feature in enumerate(critical_features):
        prefix = f"qualityContract.criticalFeatures[{index}]"
        if not isinstance(feature, dict):
            errors.append(f"{prefix} must be an object")
            continue
        feature_id = require_string(feature.get("id"), f"{prefix}.id", errors)
        contract_feature_ids.add(feature_id)
        critical_role = critical_closeup_role(feature_id)
        if critical_role in contract_critical_roles:
            errors.append(
                f"{prefix}.id collides case-insensitively with another critical "
                f"evidence role: {critical_role}"
            )
        contract_critical_roles.add(critical_role)
        if feature_id not in observed_ids:
            errors.append(f"{prefix}.id must identify an observed feature")
        require_string(feature.get("description"), f"{prefix}.description", errors)
        require_nonempty_list(feature.get("evidenceRefs"), f"{prefix}.evidenceRefs", errors)
        require_confidence(
            feature.get("threshold", contract.get("criticalThreshold")),
            f"{prefix}.threshold",
            errors,
        )
        passes = feature.get("passes", [])
        if not isinstance(passes, list):
            errors.append(f"{prefix}.passes must be a list")
        elif set(passes) - PASS_IDS:
            errors.append(f"{prefix}.passes contains unknown passes: {sorted(set(passes) - PASS_IDS)}")
    mapped_critical_ids = {
        item.get("featureId")
        for item in feature_contract
        if isinstance(item, dict) and item.get("critical") is True
    }
    if contract_feature_ids != mapped_critical_ids:
        errors.append(
            "qualityContract.criticalFeatures must exactly match critical featureContract entries"
        )

    required_views = require_nonempty_list(
        contract.get("requiredViews"), "qualityContract.requiredViews", errors
    )
    required_view_set = {
        canonical_role(str(item)) for item in required_views
    }
    missing_baseline = set(BASE_VIEW_ROLES) - required_view_set
    if missing_baseline:
        errors.append(
            f"qualityContract.requiredViews is missing baseline roles: {sorted(missing_baseline)}"
        )
    require_bool(contract.get("backReviewRequired"), "qualityContract.backReviewRequired", errors)
    if "architecture-environment" in routes:
        missing_arch = set(ARCHITECTURE_VIEW_ROLES) - required_view_set
        if missing_arch:
            errors.append(
                f"Architecture/environment contract is missing orthographic/back roles: {sorted(missing_arch)}"
            )
    elif contract.get("backReviewRequired") is True and "back" not in required_view_set:
        errors.append("qualityContract.requiredViews must include back when backReviewRequired is true")
    require_nonempty_list(contract.get("failureModes"), "qualityContract.failureModes", errors)
    require_nonempty_list(contract.get("deliverables"), "qualityContract.deliverables", errors)
    require_confidence(contract.get("globalThreshold"), "qualityContract.globalThreshold", errors)
    require_confidence(contract.get("criticalThreshold"), "qualityContract.criticalThreshold", errors)

    suggested = DETAIL_MINIMUMS.get(state.get("complexity"))
    if isinstance(minimum, int) and suggested and minimum < suggested:
        warnings.append(
            f"detailInventory.minimum {minimum} is below required guidance {suggested} "
            f"for {state['complexity']} complexity"
        )
    return errors, warnings


def command_init(args: argparse.Namespace) -> int:
    project_dir = Path(args.project_dir).expanduser().resolve()
    state_path = project_dir / "reconstruction-state.json"
    spec_path = project_dir / "reconstruction-spec.json"
    if state_path.exists() or spec_path.exists():
        raise ValueError(f"Refusing to overwrite existing reconstruction files in {project_dir}")

    reference_records = []
    for index, value in enumerate(args.reference):
        record = evidence_record(value)
        record["id"] = f"ref-{index + 1:02d}"
        record["role"] = "primary" if index == 0 else "supplemental"
        reference_records.append(record)

    for directory in ("blender", "renders", "reviews", "exports"):
        (project_dir / directory).mkdir(parents=True, exist_ok=True)

    created = utc_now()
    routes = list(dict.fromkeys(args.subject_route))
    required_views = list(BASE_VIEW_ROLES)
    if "architecture-environment" in routes:
        required_views.extend(ARCHITECTURE_VIEW_ROLES)
    spec = {
        "schemaVersion": SCHEMA_VERSION,
        "projectName": args.name,
        "target": args.target,
        "taskMode": args.task_mode,
        "validationScope": args.validation_scope,
        "designIntent": {},
        "geometryInvariants": [],
        "inspectionPlan": [],
        "complexity": args.complexity,
        "createdAt": created,
        "updatedAt": created,
        "references": reference_records,
        "subjectRoutes": routes,
        "referenceAnalysis": {
            "suitability": "unset",
            "classification": {"primaryType": "", "domain": "", "confidence": None},
            "observations": [],
            "observedFeatures": [],
            "inferences": [],
            "cameraEvidence": {},
            "scaleEvidence": {},
            "contradictions": [],
        },
        "componentPlan": [],
        "materialPlan": [],
        "featureContract": [],
        "detailInventory": {
            "scanMethod": "",
            "minimum": DETAIL_MINIMUMS[args.complexity],
            "items": [],
        },
        "unknowns": [],
        "qualityContract": {
            "definitionOfDone": [],
            "criticalFeatures": [],
            "requiredViews": required_views,
            "backReviewRequired": "architecture-environment" in routes,
            "failureModes": [],
            "deliverables": [],
            "globalThreshold": args.global_threshold,
            "criticalThreshold": args.critical_threshold,
        },
    }
    passes = []
    for index, definition in enumerate(PASS_DEFS):
        passes.append(
            {
                "id": definition["id"],
                "label": definition["label"],
                "status": "unlocked" if index == 0 else "locked",
                "reviewCount": 0,
                "builderId": None,
                "criticRounds": [],
                "corrections": [],
                "reviewHistory": [],
            }
        )
    state = {
        "schemaVersion": SCHEMA_VERSION,
        "skill": "img2blender",
        "projectName": args.name,
        "projectDir": str(project_dir),
        "specPath": str(spec_path),
        "target": args.target,
        "complexity": args.complexity,
        "status": "active",
        "currentPass": "intake",
        "criticPolicy": {
            "minimumRoundsPerVisualPass": min_critic_rounds(args.complexity),
            "maximumRoundsPerPass": args.max_critic_rounds,
            "plateauDelta": args.plateau_delta,
            "usedContextIds": [],
        },
        "createdAt": created,
        "updatedAt": created,
        "passes": passes,
    }
    append_transition(
        state,
        "project-initialized",
        {
            "projectName": args.name,
            "complexity": args.complexity,
            "referenceHashes": {
                item["id"]: item["sha256"] for item in reference_records
            },
        },
    )
    atomic_write_json(spec_path, spec)
    atomic_write_json(state_path, state)
    print(f"Created: {state_path}")
    print(f"Created: {spec_path}")
    print("Unlocked pass: intake")
    print("Next: fill the reconstruction contract, validate it, then record intake.")
    return 0


def migrate_spec_v1(spec: dict[str, Any], state: dict[str, Any]) -> dict[str, Any]:
    migrated = json.loads(json.dumps(spec))
    migrated["schemaVersion"] = SCHEMA_VERSION
    for index, reference in enumerate(migrated.get("references", [])):
        if isinstance(reference, dict):
            reference.setdefault("id", f"ref-{index + 1:02d}")
    routes = migrated.setdefault("subjectRoutes", [])
    analysis = migrated.setdefault("referenceAnalysis", {})
    inventory_items = migrated.get("detailInventory", {}).get("items", [])
    observed_features = analysis.setdefault("observedFeatures", [])
    if not observed_features:
        for index, item in enumerate(inventory_items):
            if not isinstance(item, dict):
                continue
            observed_features.append(
                {
                    "id": item.get("id") or f"migrated-feature-{index + 1:02d}",
                    "particular": item.get("region") or item.get("kind") or "migrated observed feature",
                    "evidenceRefs": [item.get("evidenceRef")]
                    if item.get("evidenceRef")
                    else ["ref-01"],
                    "confidence": item.get("confidence", 0.5),
                }
            )
    feature_contract = migrated.setdefault("featureContract", [])
    if not feature_contract:
        item_by_id = {
            item.get("id"): item for item in inventory_items if isinstance(item, dict)
        }
        for observed in observed_features:
            feature_id = observed.get("id")
            detail = item_by_id.get(feature_id, {})
            feature_contract.append(
                {
                    "featureId": feature_id,
                    "observedParticular": observed.get("particular", "migrated feature"),
                    "implementation": {
                        "kind": "deferred",
                        "target": detail.get("mapsTo", "REQUIRES-MIGRATION"),
                    },
                    "subjectChecklistItems": [],
                    "reviewCameras": [detail.get("reviewView", "reference-match")],
                    "confidence": observed.get("confidence", 0.5),
                    "evidenceRefs": observed.get("evidenceRefs", ["ref-01"]),
                    "critical": False,
                }
            )
    contract = migrated.setdefault("qualityContract", {})
    old_views = {str(item) for item in contract.get("requiredViews", [])}
    contract["requiredViews"] = list(
        dict.fromkeys(
            list(BASE_VIEW_ROLES)
            + (["back"] if "back" in old_views else [])
        )
    )
    contract["backReviewRequired"] = "back" in old_views
    migrated["migrationNotes"] = [
        "Schema v1 was upgraded without inventing subject classification.",
        "Set subjectRoutes and featureContract.subjectChecklistItems.",
        "Replace migrated deferred implementation targets with explicit scene targets.",
        "Review requiredViews and backReviewRequired before validating.",
    ]
    migrated["updatedAt"] = utc_now()
    return migrated


def command_migrate(args: argparse.Namespace) -> int:
    state_path, state = load_state(args.state, allow_legacy=True)
    if state.get("schemaVersion") == SCHEMA_VERSION:
        print("State is already schema v2; no migration needed.")
        return 0
    spec_path = Path(state["specPath"])
    spec = read_json(spec_path)
    if spec.get("schemaVersion") != LEGACY_SCHEMA_VERSION:
        raise ValueError("State is v1 but reconstruction spec is not schema v1")
    backup_state = state_path.with_suffix(".v1.json")
    backup_spec = spec_path.with_suffix(".v1.json")
    if backup_state.exists() or backup_spec.exists():
        raise ValueError("Migration backup already exists; refusing to overwrite it")
    atomic_write_json(backup_state, state)
    atomic_write_json(backup_spec, spec)
    migrated_spec = migrate_spec_v1(spec, state)
    state["schemaVersion"] = SCHEMA_VERSION
    state["criticPolicy"] = {
        "minimumRoundsPerVisualPass": min_critic_rounds(state.get("complexity", "complex")),
        "maximumRoundsPerPass": 4,
        "plateauDelta": 0.02,
        "usedContextIds": [],
    }
    legacy_by_id = {
        record.get("id"): record
        for record in state.get("passes", [])
        if isinstance(record, dict) and record.get("id") in PASS_IDS
    }
    canonical_passes: list[dict[str, Any]] = []
    for index, definition in enumerate(PASS_DEFS):
        legacy = legacy_by_id.get(definition["id"], {})
        status = "unlocked" if index == 0 else "locked"
        canonical_passes.append(
            {
                "id": definition["id"],
                "label": definition["label"],
                "status": status,
                "reviewCount": 0,
                "builderId": None,
                "criticRounds": [],
                "corrections": [],
                "reviewHistory": [],
                "legacyHistory": {
                    "status": legacy.get("status"),
                    "reviewCount": legacy.get("reviewCount", 0),
                }
                if legacy
                else None,
            }
        )
    state["passes"] = canonical_passes
    state["currentPass"] = "intake"
    state["status"] = "active"
    state.pop("completedAt", None)
    state.pop("stoppedAt", None)
    state.pop("approvedContract", None)
    state["transitionLedger"] = []
    append_transition(
        state,
        "legacy-project-migrated",
        {
            "legacyStateBackup": str(backup_state),
            "legacySpecBackup": str(backup_spec),
            "disposition": "full-intake-and-visual-revalidation-required",
        },
    )
    state["updatedAt"] = utc_now()
    atomic_write_json(spec_path, migrated_spec)
    atomic_write_json(state_path, state)
    print(f"Migrated state and spec to schema v{SCHEMA_VERSION}.")
    print(f"Backup: {backup_state}")
    print(f"Backup: {backup_spec}")
    print("Migration is structural; fill subject routes/checklist mappings before validation.")
    return 0


def status_payload(state: dict[str, Any]) -> dict[str, Any]:
    current_id = state.get("currentPass")
    current = pass_state(state, current_id) if current_id else None
    definition = pass_definition(current_id) if current_id else None
    spec = read_json(Path(state["specPath"])) if current_id else {}
    return {
        "projectName": state.get("projectName"),
        "status": state.get("status"),
        "currentPass": current_id,
        "currentLabel": definition.get("label") if definition else None,
        "builderId": current.get("builderId") if current else None,
        "criticRounds": len(current.get("criticRounds", [])) if current else None,
        "corrections": len(current.get("corrections", [])) if current else None,
        "minimumCriticRounds": (
            state.get("criticPolicy", {}).get("minimumRoundsPerVisualPass")
            if current_id and current_id != "intake"
            else 0
        ),
        "maximumCriticRounds": state.get("criticPolicy", {}).get("maximumRoundsPerPass"),
        "requiredViewRoles": required_view_roles(spec, current_id) if current_id else {},
        "taskMode": spec.get("taskMode", "faithful-reconstruction"),
        "validationScope": spec.get("validationScope", "visual-asset"),
        "requiredInvariants": [row["id"] for row in applicable_invariants(spec, current_id)] if current_id and current_id != "intake" else [],
        "auditRequired": bool(definition.get("auditStage")) if definition else False,
        "auditStage": definition.get("auditStage") if definition else None,
        "specPath": state.get("specPath"),
        "updatedAt": state.get("updatedAt"),
    }


def command_status(args: argparse.Namespace) -> int:
    _, state = load_state(args.state)
    payload = status_payload(state)
    if args.json:
        print(json.dumps(payload, indent=2))
        return 0
    print(f"Project: {payload['projectName']}")
    print(f"Status: {payload['status']}")
    if payload["currentPass"]:
        print(f"Unlocked pass: {payload['currentPass']} — {payload['currentLabel']}")
        print(f"Builder: {payload['builderId'] or 'unassigned'}")
        print(
            f"Critic rounds: {payload['criticRounds']} "
            f"(minimum {payload['minimumCriticRounds']}, maximum {payload['maximumCriticRounds']})"
        )
        print(f"Corrections: {payload['corrections']}")
        if payload["requiredViewRoles"]:
            print(
                "Required evidence: "
                + ", ".join(
                    f"{role}({kind})" for role, kind in payload["requiredViewRoles"].items()
                )
            )
        print("Scene audit required: " + ("yes" if payload["auditRequired"] else "no"))
    else:
        print("No unlocked pass remains.")
    print(f"Spec: {payload['specPath']}")
    return 0


def command_validate(args: argparse.Namespace) -> int:
    _, state = load_state(args.state)
    errors, warnings = validate_spec(state)
    for warning in warnings:
        print(f"WARNING: {warning}")
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        print(f"Validation failed with {len(errors)} error(s).")
        return 1
    print("Validation passed.")
    return 0


def validate_evidence(
    report: dict[str, Any],
    render_records: list[dict[str, Any]],
    comparison_records: list[dict[str, Any]],
    required_roles: dict[str, str],
    action: str,
) -> None:
    admitted = {
        (record["role"], record["kind"], record["path"]): record
        for record in render_records + comparison_records
    }
    views = report.get("viewEvidence")
    if not isinstance(views, list):
        raise ValueError("critic report viewEvidence must be a list")
    seen: set[tuple[str, str]] = set()
    for index, view in enumerate(views):
        if not isinstance(view, dict):
            raise ValueError(f"critic report viewEvidence[{index}] must be an object")
        role = canonical_role(
            require_report_string(view.get("role"), f"viewEvidence[{index}].role")
        )
        kind = require_report_string(view.get("kind"), f"viewEvidence[{index}].kind").lower()
        path = str(Path(require_report_string(view.get("path"), f"viewEvidence[{index}].path")).expanduser().resolve())
        if (role, kind) in seen:
            raise ValueError(f"Duplicate critic report evidence role/kind: {role}/{kind}")
        seen.add((role, kind))
        if (role, kind, path) not in admitted:
            raise ValueError(
                f"Critic report evidence was not admitted by matching --{kind}: {role}={path}"
            )
        if not isinstance(view.get("judgeable"), bool):
            raise ValueError(f"viewEvidence[{index}].judgeable must be a boolean")
        if not view.get("judgeable") and not str(view.get("notes", "")).strip():
            raise ValueError(f"viewEvidence[{index}] needs notes when not judgeable")
    view_by_role_kind = {
        (
            canonical_role(str(view.get("role", ""))),
            str(view.get("kind", "")).strip().lower(),
        ): view
        for view in views
        if isinstance(view, dict)
    }
    if action != "request-input":
        for role, kind in required_roles.items():
            if (role, kind) not in seen:
                raise ValueError(f"Missing required {kind} evidence role: {role}")
            if view_by_role_kind[(role, kind)].get("judgeable") is not True:
                raise ValueError(f"Required evidence must be positively judgeable: {role}")

    sufficiency = report.get("evidenceSufficiency")
    if not isinstance(sufficiency, dict):
        raise ValueError("critic report evidenceSufficiency must be an object")
    if not isinstance(sufficiency.get("sufficient"), bool):
        raise ValueError("evidenceSufficiency.sufficient must be a boolean")
    if not isinstance(sufficiency.get("missingOrUnjudgeable"), list):
        raise ValueError("evidenceSufficiency.missingOrUnjudgeable must be a list")
    require_report_string(sufficiency.get("rationale"), "evidenceSufficiency.rationale")


def validate_review_bundle(
    checkpoint: dict[str, Any],
    render_manifest_record: dict[str, Any],
    comparison_manifest_record: dict[str, Any],
    render_records: list[dict[str, Any]],
    comparison_records: list[dict[str, Any]],
    current: dict[str, Any],
    spec: dict[str, Any],
) -> None:
    checkpoint_path = Path(checkpoint["path"])
    if checkpoint_path.suffix.lower() != ".blend":
        raise ValueError("Review checkpoint must be a .blend file")

    render_manifest = read_json(Path(render_manifest_record["path"]))
    if render_manifest.get("schemaVersion") != SCHEMA_VERSION:
        raise ValueError("Render manifest schemaVersion must be 2")
    manifest_blend = render_manifest.get("blendFile")
    if not isinstance(manifest_blend, str) or (
        Path(manifest_blend).expanduser().resolve() != checkpoint_path
    ):
        raise ValueError("Render manifest blendFile must match the reviewed checkpoint")
    if render_manifest.get("blendSha256") != checkpoint["sha256"]:
        raise ValueError("Render manifest blendSha256 must match the reviewed checkpoint")
    manifest_renders = render_manifest.get("renders")
    if not isinstance(manifest_renders, list):
        raise ValueError("Render manifest renders must be a list")
    manifest_by_role: dict[str, dict[str, Any]] = {}
    for index, item in enumerate(manifest_renders):
        if not isinstance(item, dict):
            raise ValueError(f"Render manifest renders[{index}] must be an object")
        role = canonical_role(
            require_report_string(
                item.get("role"), f"render manifest renders[{index}].role"
            )
        )
        if role in manifest_by_role:
            raise ValueError(f"Render manifest contains duplicate role: {role}")
        path = Path(
            require_report_string(
                item.get("path"), f"render manifest renders[{index}].path"
            )
        ).expanduser().resolve()
        if not path.is_file() or sha256_file(path) != item.get("sha256"):
            raise ValueError(f"Render manifest hash mismatch for role {role}")
        matrix = item.get("cameraMatrixWorld")
        if (
            not isinstance(matrix, list)
            or len(matrix) != 4
            or any(not isinstance(row, list) or len(row) != 4 for row in matrix)
        ):
            raise ValueError(f"Render manifest role {role} lacks a 4x4 camera matrix")
        role_state = item.get("roleState")
        if not isinstance(role_state, dict) or not str(role_state.get("viewLayer", "")).strip():
            raise ValueError(f"Render manifest role {role} lacks role-state/view-layer provenance")
        if role == "clay-silhouette" and not role_state.get("materialOverride"):
            raise ValueError("clay-silhouette manifest needs a material override")
        if role == "neutral-material" and role_state.get("lightRig") != "neutral":
            raise ValueError("neutral-material manifest needs lightRig=neutral")
        if role == "grazing-light" and role_state.get("lightRig") != "grazing":
            raise ValueError("grazing-light manifest needs lightRig=grazing")
        if role.startswith("ortho-") and item.get("cameraType") != "ORTHO":
            raise ValueError(f"Architecture evidence role {role} must use an orthographic camera")
        manifest_by_role[role] = item
    settings = render_manifest.get("settings")
    required_settings = {
        "engine",
        "samples",
        "seed",
        "resolution",
        "resolutionPercentage",
        "viewTransform",
        "look",
        "displayDevice",
        "exposure",
    }
    if not isinstance(settings, dict) or required_settings - set(settings):
        raise ValueError(
            "Render manifest lacks complete deterministic settings: "
            f"{sorted(required_settings - set(settings or {}))}"
        )
    if current.get("criticRounds"):
        prior_manifest_path = Path(
            current["criticRounds"][-1]["renderManifest"]["path"]
        )
        prior_settings = read_json(prior_manifest_path).get("settings")
        if settings != prior_settings:
            raise ValueError("Render settings changed between critic rounds")
    for record in render_records:
        item = manifest_by_role.get(record["role"])
        if not item:
            raise ValueError(f"Admitted render role missing from manifest: {record['role']}")
        if Path(item["path"]).expanduser().resolve() != Path(record["path"]):
            raise ValueError(f"Render manifest path mismatch for role {record['role']}")
        if item.get("sha256") != record["sha256"]:
            raise ValueError(f"Render manifest/admitted hash mismatch for role {record['role']}")

    comparison_manifest = read_json(Path(comparison_manifest_record["path"]))
    if comparison_manifest.get("schemaVersion") != SCHEMA_VERSION:
        raise ValueError("Comparison manifest schemaVersion must be 2")
    comparison_items = comparison_manifest.get("evidence")
    if not isinstance(comparison_items, list):
        raise ValueError("Comparison manifest evidence must be a list")
    comparison_by_role: dict[str, dict[str, Any]] = {}
    for index, item in enumerate(comparison_items):
        if not isinstance(item, dict):
            raise ValueError(
                f"Comparison manifest evidence[{index}] must be an object"
            )
        role = canonical_role(
            require_report_string(
                item.get("role"), f"comparison manifest evidence[{index}].role"
            )
        )
        if role in comparison_by_role:
            raise ValueError(
                f"Comparison manifest contains duplicate canonical role: {role}"
            )
        comparison_by_role[role] = item
    for record in comparison_records:
        item = comparison_by_role.get(record["role"])
        if not isinstance(item, dict):
            raise ValueError(
                f"Admitted comparison role missing from manifest: {record['role']}"
            )
        if Path(str(item.get("path", ""))).expanduser().resolve() != Path(record["path"]):
            raise ValueError(f"Comparison manifest path mismatch for role {record['role']}")
        if item.get("sha256") != record["sha256"]:
            raise ValueError(
                f"Comparison manifest/admitted hash mismatch for role {record['role']}"
            )
    inputs = comparison_manifest.get("inputs")
    if not isinstance(inputs, dict):
        raise ValueError("Comparison manifest inputs must be an object")
    reference_input = inputs.get("reference")
    admitted_references = {
        (
            str(Path(item["path"]).expanduser().resolve()),
            item.get("sha256"),
        )
        for item in spec.get("references", [])
        if isinstance(item, dict) and item.get("path")
    }
    if (
        not isinstance(reference_input, dict)
        or (
            str(Path(str(reference_input.get("path", ""))).expanduser().resolve()),
            reference_input.get("sha256"),
        )
        not in admitted_references
    ):
        raise ValueError(
            "Comparison manifest reference input must match an admitted pinned reference"
        )
    current_input = inputs.get("current")
    reference_render = next(
        (item for item in render_records if item["role"] == "reference-match"),
        None,
    )
    if reference_render and (
        not isinstance(current_input, dict)
        or Path(str(current_input.get("path", ""))).expanduser().resolve()
        != Path(reference_render["path"])
        or current_input.get("sha256") != reference_render["sha256"]
    ):
        raise ValueError(
            "Comparison manifest current input must be the admitted reference-match render"
        )
    rounds = current.get("criticRounds", [])
    if rounds:
        previous_render = next(
            (
                item
                for item in rounds[-1].get("renders", [])
                if item.get("role") == "reference-match"
            ),
            None,
        )
        previous_input = inputs.get("previous")
        if previous_render and (
            not isinstance(previous_input, dict)
            or Path(str(previous_input.get("path", ""))).expanduser().resolve()
            != Path(previous_render["path"])
            or previous_input.get("sha256") != previous_render["sha256"]
        ):
            raise ValueError(
                "Comparison manifest previous input must be the prior round's "
                "reference-match render"
            )
    else:
        start_render = current.get("startReferenceRender")
        previous_input = inputs.get("previous")
        if (
            not isinstance(start_render, dict)
            or not isinstance(previous_input, dict)
            or Path(str(previous_input.get("path", ""))).expanduser().resolve()
            != Path(start_render["path"])
            or previous_input.get("sha256") != start_render["sha256"]
        ):
            raise ValueError(
                "First-round comparison previous input must match the pinned "
                "start-of-pass reference render"
            )

    corrections = current.get("corrections", [])
    if corrections:
        expected_checkpoint = next(
            (
                item.get("checkpoint")
                for item in reversed(corrections)
                if isinstance(item, dict) and item.get("checkpoint")
            ),
            None,
        )
        if expected_checkpoint and checkpoint["sha256"] != expected_checkpoint.get("sha256"):
            raise ValueError("Reviewed checkpoint must match the latest recorded correction")
    elif current.get("startCheckpoint") and checkpoint["sha256"] != current["startCheckpoint"].get("sha256"):
        raise ValueError("First-round checkpoint changed without a recorded correction")


def require_report_string(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"critic report {field} must be a non-empty string")
    return value.strip()


def validate_checklist(
    report: dict[str, Any],
    routes: list[str],
    action: str,
    available_roles: set[str],
) -> None:
    universal = report.get("universalChecklist")
    if not isinstance(universal, list):
        raise ValueError("critic report universalChecklist must be a list")
    subject = report.get("subjectChecklist")
    if not isinstance(subject, list):
        raise ValueError("critic report subjectChecklist must be a list")

    def inspect(
        records: list[Any],
        required: set[str],
        field: str,
    ) -> None:
        by_id: dict[str, dict[str, Any]] = {}
        for index, item in enumerate(records):
            if not isinstance(item, dict):
                raise ValueError(f"{field}[{index}] must be an object")
            item_id = require_report_string(item.get("id"), f"{field}[{index}].id")
            if item_id in by_id:
                raise ValueError(f"Duplicate {field} id: {item_id}")
            status = item.get("status")
            if status not in {"pass", "fail", "not-applicable"}:
                raise ValueError(f"{field}[{index}].status must be pass, fail, or not-applicable")
            require_report_string(item.get("notes"), f"{field}[{index}].notes")
            evidence_roles_raw = item.get("evidenceRoles")
            if not isinstance(evidence_roles_raw, list):
                raise ValueError(f"{field}[{index}].evidenceRoles must be a list")
            if status != "not-applicable" and not evidence_roles_raw:
                raise ValueError(f"{field}[{index}] needs evidenceRoles unless not-applicable")
            evidence_roles = {
                canonical_role(str(role)) for role in evidence_roles_raw
            }
            unknown_evidence = sorted(set(evidence_roles) - available_roles)
            if unknown_evidence:
                raise ValueError(
                    f"{field}[{index}].evidenceRoles cites unadmitted roles: "
                    f"{unknown_evidence}"
                )
            by_id[item_id] = item
        missing = required - set(by_id)
        extra = set(by_id) - required
        if missing or extra:
            raise ValueError(f"{field} ids mismatch; missing={sorted(missing)}, extra={sorted(extra)}")
        if action == "continue":
            not_passed = sorted(
                item_id for item_id, item in by_id.items() if item["status"] != "pass"
            )
            if not_passed:
                raise ValueError(
                    f"Continue requires every {field} item to pass positively: {not_passed}"
                )

    inspect(universal, set(UNIVERSAL_CHECKS), "universalChecklist")
    required_subject = {
        check for route in routes for check in SUBJECT_CHECKS.get(route, ())
    }
    inspect(subject, required_subject, "subjectChecklist")


def validate_hard_gates(
    report: dict[str, Any], action: str, available_roles: set[str]
) -> None:
    gates = report.get("hardGates")
    if not isinstance(gates, list):
        raise ValueError("critic report hardGates must be a list")
    by_id: dict[str, dict[str, Any]] = {}
    for index, gate in enumerate(gates):
        if not isinstance(gate, dict):
            raise ValueError(f"hardGates[{index}] must be an object")
        gate_id = require_report_string(gate.get("id"), f"hardGates[{index}].id")
        if gate_id in by_id:
            raise ValueError(f"Duplicate hard gate id: {gate_id}")
        if gate.get("status") not in {"pass", "fail", "not-applicable"}:
            raise ValueError(f"hardGates[{index}].status must be pass, fail, or not-applicable")
        require_report_string(gate.get("finding"), f"hardGates[{index}].finding")
        evidence_roles_raw = gate.get("evidenceRoles")
        if not isinstance(evidence_roles_raw, list):
            raise ValueError(f"hardGates[{index}].evidenceRoles must be a list")
        evidence_roles = {
            canonical_role(str(role)) for role in evidence_roles_raw
        }
        unknown_evidence = sorted(evidence_roles - available_roles)
        if unknown_evidence:
            raise ValueError(
                f"hardGates[{index}].evidenceRoles cites unadmitted roles: "
                f"{unknown_evidence}"
            )
        by_id[gate_id] = gate
    missing = set(MANDATORY_HARD_GATES) - set(by_id)
    if missing:
        raise ValueError(f"Missing mandatory hard gates: {sorted(missing)}")
    if action == "continue":
        not_passed = sorted(
            gate_id for gate_id, gate in by_id.items() if gate["status"] != "pass"
        )
        if not_passed:
            raise ValueError(
                f"Hard gates override total score and must pass positively: {not_passed}"
            )


def validate_critical_features(
    report: dict[str, Any],
    contract: dict[str, Any],
    pass_id: str,
    action: str,
    available_roles: set[str],
) -> None:
    reviews = report.get("criticalFeatures")
    if not isinstance(reviews, list):
        raise ValueError("critic report criticalFeatures must be a list")
    by_id = {
        item.get("id"): item for item in reviews if isinstance(item, dict) and item.get("id")
    }
    for feature in critical_for_pass(contract, pass_id):
        feature_id = feature["id"]
        review = by_id.get(feature_id)
        if not isinstance(review, dict):
            raise ValueError(f"Missing critical feature review: {feature_id}")
        score = score_number(review.get("score"), f"criticalFeatures[{feature_id}].score")
        for bool_field in (
            "visible",
            "supported",
            "attached",
            "freeOfIntersection",
            "multiViewConsistent",
            "onlyReferenceCamera",
        ):
            if not isinstance(review.get(bool_field), bool):
                raise ValueError(f"criticalFeatures[{feature_id}].{bool_field} must be boolean")
        evidence_roles_raw = review.get("evidenceRoles")
        if not isinstance(evidence_roles_raw, list) or not evidence_roles_raw:
            raise ValueError(f"criticalFeatures[{feature_id}].evidenceRoles must be non-empty")
        evidence_roles = {
            canonical_role(str(role)) for role in evidence_roles_raw
        }
        unknown_evidence = sorted(evidence_roles - available_roles)
        if unknown_evidence:
            raise ValueError(
                f"criticalFeatures[{feature_id}].evidenceRoles cites unadmitted roles: "
                f"{unknown_evidence}"
            )
        require_report_string(review.get("notes"), f"criticalFeatures[{feature_id}].notes")
        threshold = score_number(
            feature.get("threshold", contract.get("criticalThreshold")),
            f"qualityContract.criticalFeatures[{feature_id}].threshold",
        )
        invalid = (
            score < threshold
            or not review["visible"]
            or not review["supported"]
            or not review["attached"]
            or not review["freeOfIntersection"]
            or not review["multiViewConsistent"]
            or review["onlyReferenceCamera"]
        )
        if action == "continue" and invalid:
            raise ValueError(
                f"Critical feature {feature_id} cannot pass: threshold/visibility/support/"
                "attachment/intersection/multi-view gate failed"
            )


def validate_scores_and_delta(
    report: dict[str, Any],
    contract: dict[str, Any],
    previous: dict[str, Any] | None,
    action: str,
) -> float:
    scorecard = report.get("scorecard")
    if not isinstance(scorecard, dict):
        raise ValueError("critic report scorecard must be an object")
    overall = score_number(scorecard.get("overall"), "scorecard.overall")
    layers = scorecard.get("layers")
    if not isinstance(layers, dict):
        raise ValueError("scorecard.layers must be an object")
    for layer in UNIVERSAL_CHECKS:
        score_number(layers.get(layer), f"scorecard.layers.{layer}")
    priority_weights = scorecard.get("priorityWeights")
    if not isinstance(priority_weights, dict) or len(priority_weights) < 2:
        raise ValueError("scorecard.priorityWeights must contain at least two explicit priorities")
    total_weight = 0.0
    for key, value in priority_weights.items():
        total_weight += score_number(value, f"scorecard.priorityWeights.{key}")
    if abs(total_weight - 1.0) > 0.001:
        raise ValueError("scorecard.priorityWeights must sum to 1.0")
    require_report_string(scorecard.get("overallRationale"), "scorecard.overallRationale")
    if scorecard.get("aggregation") != "hard-gates-then-weighted-judgment":
        raise ValueError(
            "scorecard.aggregation must be hard-gates-then-weighted-judgment"
        )
    delta = report.get("deltaFromPrior")
    if not isinstance(delta, dict):
        raise ValueError("critic report deltaFromPrior must be an object")
    if previous is None:
        if delta.get("overall") is not None:
            raise ValueError("First critic round deltaFromPrior.overall must be null")
    else:
        prior_overall = score_number(
            previous["report"]["scorecard"]["overall"], "previous scorecard.overall"
        )
        supplied_delta = delta.get("overall")
        if not isinstance(supplied_delta, (int, float)) or isinstance(supplied_delta, bool):
            raise ValueError("deltaFromPrior.overall must be numeric after the first round")
        expected_delta = overall - prior_overall
        if abs(float(supplied_delta) - expected_delta) > 0.005:
            raise ValueError(
                f"deltaFromPrior.overall {supplied_delta} does not match computed {expected_delta:.3f}"
            )
    if not isinstance(delta.get("criticalFeatures"), dict):
        raise ValueError("deltaFromPrior.criticalFeatures must be an object")
    require_report_string(delta.get("summary"), "deltaFromPrior.summary")
    if action == "continue":
        threshold = score_number(contract.get("globalThreshold"), "qualityContract.globalThreshold")
        if overall < threshold:
            raise ValueError(f"Overall score {overall:.3f} is below threshold {threshold:.3f}")
    return overall


def detect_plateau(
    current_report: dict[str, Any],
    previous_rounds: list[dict[str, Any]],
    plateau_delta: float,
) -> bool:
    current_delta = current_report.get("deltaFromPrior", {}).get("overall")
    if len(previous_rounds) < 2 or not isinstance(current_delta, (int, float)):
        return False
    prior_delta = (
        previous_rounds[-1]
        .get("report", {})
        .get("deltaFromPrior", {})
        .get("overall")
    )
    return (
        isinstance(prior_delta, (int, float))
        and abs(float(current_delta)) < plateau_delta
        and abs(float(prior_delta)) < plateau_delta
    )


def validate_critic_report(
    report: dict[str, Any],
    state: dict[str, Any],
    current: dict[str, Any],
    spec: dict[str, Any],
    action: str,
    renders: list[dict[str, Any]],
    comparisons: list[dict[str, Any]],
    checkpoint: dict[str, Any],
) -> None:
    if report.get("schemaVersion") != SCHEMA_VERSION:
        raise ValueError(f"critic report schemaVersion must be {SCHEMA_VERSION}")
    if report.get("contractSha256") != state.get("approvedContract", {}).get("sha256"):
        raise ValueError("Critic report contractSha256 does not match the pinned contract")
    if report.get("checkpointSha256") != checkpoint.get("sha256"):
        raise ValueError("Critic report checkpointSha256 does not match the reviewed checkpoint")
    critic = report.get("critic")
    if not isinstance(critic, dict):
        raise ValueError("critic report critic must be an object")
    critic_id = require_report_string(critic.get("id"), "critic.id")
    context_id = require_report_string(critic.get("contextId"), "critic.contextId")
    if critic.get("role") != "independent-visual-critic":
        raise ValueError(
            "Only an independent-visual-critic counts toward pass review; "
            "forensic critics are advisory"
        )
    if critic.get("authoredCurrentPass") is not False:
        raise ValueError("critic.authoredCurrentPass must be false")
    builder_id = current.get("builderId")
    if not builder_id:
        raise ValueError("Current pass has no assigned builder")
    if critic_id == builder_id or context_id == builder_id:
        raise ValueError("The builder cannot review or approve the current pass")
    rounds = current.get("criticRounds", [])
    if any(item.get("criticId") == critic_id for item in rounds):
        raise ValueError("Each critique round requires a fresh critic identity")
    if context_id in state.get("criticPolicy", {}).get("usedContextIds", []):
        raise ValueError("Each critique round requires a fresh critic context")
    if report.get("decision") != action:
        raise ValueError("critic report decision must match --action")

    required_roles = required_view_roles(spec, current["id"])
    validate_evidence(report, renders, comparisons, required_roles, action)
    available_roles = {
        canonical_role(item["role"])
        for item in renders + comparisons
        if isinstance(item.get("role"), str)
    }
    validate_checklist(report, spec.get("subjectRoutes", []), action, available_roles)
    validate_hard_gates(report, action, available_roles)
    contract = spec.get("qualityContract", {})
    validate_critical_features(
        report, contract, current["id"], action, available_roles
    )
    previous = rounds[-1] if rounds else None
    validate_scores_and_delta(report, contract, previous, action)

    finding = report.get("highestImpactFinding")
    if not isinstance(finding, dict):
        raise ValueError("critic report highestImpactFinding must be an object")
    require_report_string(finding.get("id"), "highestImpactFinding.id")
    require_report_string(finding.get("rootCause"), "highestImpactFinding.rootCause")
    require_report_string(finding.get("correctionBrief"), "highestImpactFinding.correctionBrief")
    if not isinstance(finding.get("affectedContractIds"), list):
        raise ValueError("highestImpactFinding.affectedContractIds must be a list")

    trajectory = report.get("trajectory")
    if not isinstance(trajectory, dict):
        raise ValueError("critic report trajectory must be an object")
    trajectory_status = trajectory.get("status")
    if trajectory_status not in {"first-round", "improving", "plateau", "oscillation", "regressing"}:
        raise ValueError("trajectory.status is invalid")
    require_report_string(trajectory.get("rationale"), "trajectory.rationale")
    computed_plateau = detect_plateau(
        report,
        rounds,
        float(state.get("criticPolicy", {}).get("plateauDelta", 0.02)),
    )
    if computed_plateau and trajectory_status != "plateau":
        raise ValueError("Two negligible deltas constitute a plateau and must be declared")
    if (computed_plateau or trajectory_status in {"plateau", "oscillation"}) and action not in PLATEAU_EXIT_ACTIONS:
        raise ValueError(
            "Plateau/oscillation forbids continue or another local correction; "
            "use refine-spec, request-input, or stop"
        )
    if action == "continue" and report.get("evidenceSufficiency", {}).get("sufficient") is not True:
        raise ValueError("Cannot continue with insufficient evidence")
    prior_finding_ids = {
        item.get("report", {}).get("highestImpactFinding", {}).get("id")
        for item in rounds
    }
    current_finding_id = finding["id"]
    if (
        current_finding_id in prior_finding_ids
        and action not in PLATEAU_EXIT_ACTIONS
    ):
        raise ValueError(
            "Repeated highest-impact root cause forbids continue/local correction; "
            "use refine-spec, request-input, or stop"
        )


def validate_audit(
    path: Path,
    expected_stage: str,
    checkpoint: dict[str, Any],
    required_roles: dict[str, str],
) -> None:
    audit = read_json(path)
    if audit.get("schemaVersion") != SCHEMA_VERSION:
        raise ValueError(f"Audit schemaVersion must be {SCHEMA_VERSION}: {path}")
    if audit.get("stage") != expected_stage:
        raise ValueError(
            f"Audit stage must be {expected_stage!r}; got {audit.get('stage')!r}: {path}"
        )
    if audit.get("strict") is not True:
        raise ValueError(f"Audit must be generated with --strict: {path}")
    if not str(audit.get("blenderVersion", "")).strip():
        raise ValueError(f"Audit must record blenderVersion: {path}")
    blend_file = audit.get("blendFile")
    if (
        not isinstance(blend_file, str)
        or Path(blend_file).expanduser().resolve() != Path(checkpoint["path"])
        or audit.get("blendSha256") != checkpoint["sha256"]
    ):
        raise ValueError(f"Audit blend provenance does not match reviewed checkpoint: {path}")
    summary = audit.get("summary")
    if not isinstance(summary, dict):
        raise ValueError(f"Audit lacks summary object: {path}")
    error_count = summary.get("errors")
    if not isinstance(error_count, int):
        raise ValueError(f"Audit summary.errors must be an integer: {path}")
    if summary.get("status") != "pass":
        raise ValueError(f"Audit summary.status must be pass: {path}")
    issues = audit.get("issues")
    if not isinstance(issues, list):
        raise ValueError(f"Audit issues must be a list: {path}")
    counted_errors = sum(
        1
        for issue in issues
        if isinstance(issue, dict) and issue.get("severity") == "error"
    )
    counted_warnings = sum(
        1
        for issue in issues
        if isinstance(issue, dict) and issue.get("severity") == "warning"
    )
    if error_count != counted_errors or summary.get("warnings") != counted_warnings:
        raise ValueError(f"Audit summary counts do not match issues: {path}")
    if error_count:
        raise ValueError(f"Audit has {error_count} unresolved error(s): {path}")
    cameras = audit.get("cameras")
    if not isinstance(cameras, list):
        raise ValueError(f"Audit cameras must be a list: {path}")
    camera_roles = {
        canonical_role(str(item.get("role")))
        for item in cameras
        if isinstance(item, dict) and item.get("role")
    }
    missing_roles = sorted(
        role
        for role, kind in required_roles.items()
        if kind == "render" and role not in camera_roles
    )
    if missing_roles:
        raise ValueError(f"Audit is missing required camera roles: {missing_roles}")


def advance_pass(state: dict[str, Any], current: dict[str, Any]) -> None:
    current["status"] = "complete"
    current["completedAt"] = utc_now()
    index = next(idx for idx, record in enumerate(state["passes"]) if record["id"] == current["id"])
    if index + 1 < len(state["passes"]):
        next_pass = state["passes"][index + 1]
        next_pass["status"] = "unlocked"
        state["currentPass"] = next_pass["id"]
        state["status"] = "active"
    else:
        state["currentPass"] = None
        state["status"] = "complete"
        state["completedAt"] = utc_now()


def command_open_pass(args: argparse.Namespace) -> int:
    state_path, state = load_state(args.state)
    if state.get("status") != "active":
        raise ValueError("A pass can only be opened while the pipeline is active")
    current_id = state.get("currentPass")
    if not current_id or current_id == "intake":
        raise ValueError("Only a visual pass can be opened")
    if args.pass_id != current_id:
        raise ValueError(f"Only the current pass may be opened: {current_id}")
    current = pass_state(state, current_id)
    if current.get("builderId") or current.get("startCheckpoint"):
        raise ValueError("Current pass is already opened")
    ensure_pinned_contract(state)
    checkpoint = evidence_record(args.start_checkpoint)
    if Path(checkpoint["path"]).suffix.lower() != ".blend":
        raise ValueError("Start checkpoint must be a .blend file")
    start_render = evidence_record(args.start_reference_render)
    builder_id = args.builder_id.strip()
    if not builder_id:
        raise ValueError("--builder-id must not be empty")
    current["builderId"] = builder_id
    current["passSessionId"] = str(uuid.uuid4())
    current["startCheckpoint"] = checkpoint
    current["startReferenceRender"] = start_render
    current["openedAt"] = utc_now()
    append_transition(
        state,
        "visual-pass-opened",
        {
            "passId": current_id,
            "passSessionId": current["passSessionId"],
            "builderId": builder_id,
            "contractSha256": state["approvedContract"]["sha256"],
            "startCheckpointSha256": checkpoint["sha256"],
            "startReferenceRenderSha256": start_render["sha256"],
        },
    )
    state["updatedAt"] = utc_now()
    atomic_write_json(state_path, state)
    print(f"Opened visual pass {current_id} for builder {builder_id}.")
    return 0


def validate_review_invariants(args, spec, checkpoint, spec_hash, pass_id):
    path = getattr(args, "invariant_report", None)
    required = applicable_invariants(spec, pass_id)
    if args.action == "continue" and required and not path:
        raise ValueError("--invariant-report is required for declared geometry invariants")
    if not path:
        return None
    record = evidence_record(path)
    validate_invariant_report(
        read_json(Path(record["path"])), spec, checkpoint["sha256"], spec_hash,
        pass_id, require_pass=args.action == "continue",
    )
    return record


def command_review(args: argparse.Namespace) -> int:
    state_path, state = load_state(args.state)
    if state.get("status") in {"complete", "stopped"}:
        raise ValueError(f"Pipeline is already {state.get('status')}")
    current_id = state.get("currentPass")
    if not current_id:
        raise ValueError("No pass is currently unlocked")
    if args.pass_id != current_id:
        raise ValueError(f"Only the unlocked pass may be reviewed: {current_id}; got {args.pass_id}")
    summary = args.summary.strip()
    if not summary:
        raise ValueError("--summary must not be empty")

    definition = pass_definition(current_id)
    current = pass_state(state, current_id)
    spec = read_json(Path(state["specPath"]))
    artifacts = [evidence_record(item) for item in args.artifact]

    if current_id == "intake":
        if args.action != "continue":
            raise ValueError("Intake review only accepts continue after validation")
        errors, warnings = validate_spec(state)
        for warning in warnings:
            print(f"WARNING: {warning}")
        if errors:
            raise ValueError("Intake spec validation failed:\n- " + "\n- ".join(errors))
        if not artifacts:
            raise ValueError("Intake continue requires --artifact reconstruction-spec.json")
        approved_spec = evidence_record(state["specPath"])
        if not any(item["sha256"] == approved_spec["sha256"] for item in artifacts):
            raise ValueError(
                "Intake artifact must include the exact validated reconstruction spec"
            )
        spec_value = read_json(Path(state["specPath"]))
        state["approvedContract"] = {
            **approved_spec,
            "referenceHashes": {
                item["id"]: item["sha256"] for item in spec_value["references"]
            },
            "approvedAt": utc_now(),
        }
        current["reviewHistory"].append(
            {
                "timestamp": utc_now(),
                "passId": current_id,
                "action": "continue",
                "summary": summary,
                "artifacts": artifacts,
            }
        )
        current["reviewCount"] += 1
        append_transition(
            state,
            "intake-approved",
            {
                "contractSha256": approved_spec["sha256"],
                "referenceHashes": state["approvedContract"]["referenceHashes"],
            },
        )
        advance_pass(state, current)
        state["updatedAt"] = utc_now()
        atomic_write_json(state_path, state)
        print("Recorded continue for intake.")
        print(f"Unlocked pass: {state['currentPass']}")
        return 0

    spec = ensure_pinned_contract(state)
    if not args.builder_id.strip():
        raise ValueError("--builder-id is required for visual passes")
    if current.get("builderId") is None or current.get("startCheckpoint") is None:
        raise ValueError(
            "Open the visual pass with open-pass before building or reviewing it"
        )
    if current["builderId"] != args.builder_id.strip():
        raise ValueError(
            f"Pass builder is already {current['builderId']}; corrections/reviews must preserve ownership"
        )

    rounds = current.get("criticRounds", [])
    corrections = current.get("corrections", [])
    if rounds and len(corrections) < len(rounds):
        raise ValueError(
            "The prior critic's single highest-impact root cause must be corrected "
            "before dispatching a fresh critic"
        )
    maximum = int(state["criticPolicy"]["maximumRoundsPerPass"])
    prospective_round_count = len(rounds) + 1
    if prospective_round_count > maximum:
        raise ValueError(
            f"Maximum critic rounds ({maximum}) reached; the pass cannot loop again"
        )
    if prospective_round_count == maximum and args.action in (
        REFINEMENT_ACTIONS | {"request-input"}
    ):
        raise ValueError(
            "The final permitted critic round cannot request another correction/input cycle; "
            "use continue or stop"
        )
    if not args.critic_report:
        raise ValueError("--critic-report is required for every visual pass review")
    if not args.checkpoint or not args.render_manifest or not args.comparison_manifest:
        raise ValueError(
            "--checkpoint, --render-manifest, and --comparison-manifest are required "
            "for every visual pass review"
        )

    renders = parse_role_evidence(args.render, "render")
    comparisons = parse_role_evidence(args.comparison, "comparison")
    checkpoint_record = evidence_record(args.checkpoint)
    render_manifest_record = evidence_record(args.render_manifest)
    comparison_manifest_record = evidence_record(args.comparison_manifest)
    validate_review_bundle(
        checkpoint_record,
        render_manifest_record,
        comparison_manifest_record,
        renders,
        comparisons,
        current,
        spec,
    )
    if args.action == "continue":
        validate_inspection_evidence(spec, read_json(Path(render_manifest_record["path"])))
    invariant_record = validate_review_invariants(
        args, spec, checkpoint_record, state["approvedContract"]["sha256"], current_id,
    )
    critic_record = evidence_record(args.critic_report)
    report = read_json(Path(critic_record["path"]))
    validate_critic_report(
        report,
        state,
        current,
        spec,
        args.action,
        renders,
        comparisons,
        checkpoint_record,
    )

    minimum = int(state["criticPolicy"]["minimumRoundsPerVisualPass"])
    if args.action == "continue" and prospective_round_count < minimum:
        raise ValueError(
            f"{state['complexity']} work requires at least {minimum} independent critic rounds "
            "per visual pass before continue"
        )
    if args.action == "continue" and definition["auditStage"]:
        if not args.audit:
            raise ValueError(f"--audit is required for {current_id}")
        validate_audit(
            Path(args.audit).expanduser().resolve(),
            definition["auditStage"],
            checkpoint_record,
            required_view_roles(spec, current_id),
        )
    audit_record = evidence_record(args.audit) if args.audit else None

    critic = report["critic"]
    round_record = {
        "round": prospective_round_count,
        "timestamp": utc_now(),
        "criticId": critic["id"],
        "criticContextId": critic["contextId"],
        "action": args.action,
        "report": report,
        "reportEvidence": critic_record,
        "checkpoint": checkpoint_record,
        "renderManifest": render_manifest_record,
        "comparisonManifest": comparison_manifest_record,
        "renders": renders,
        "comparisons": comparisons,
        "artifacts": artifacts,
        "audit": audit_record,
        "invariantReport": invariant_record,
    }
    rounds.append(round_record)
    state["criticPolicy"]["usedContextIds"].append(critic["contextId"])
    current["reviewCount"] = int(current.get("reviewCount", 0)) + 1
    current["reviewHistory"].append(
        {
            "timestamp": round_record["timestamp"],
            "action": args.action,
            "summary": summary,
            "criticRound": prospective_round_count,
            "criticId": critic["id"],
        }
    )

    if args.action == "continue":
        advance_pass(state, current)
    elif args.action == "refine-spec":
        current["status"] = "awaiting-spec-revision"
        state["status"] = "awaiting-spec-revision"
    elif args.action in {"refine-scene", "refine-camera-light"}:
        current["status"] = "awaiting-correction"
        state["status"] = "awaiting-correction"
    elif args.action == "request-input":
        current["status"] = "waiting-input"
        state["status"] = "waiting-input"
    elif args.action == "stop":
        current["status"] = "stopped"
        state["status"] = "stopped"
        state["stoppedAt"] = utc_now()

    append_transition(
        state,
        "independent-critic-round-recorded",
        {
            "passId": current_id,
            "round": prospective_round_count,
            "criticId": critic["id"],
            "criticContextId": critic["contextId"],
            "decision": args.action,
            "contractSha256": state["approvedContract"]["sha256"],
            "checkpointSha256": checkpoint_record["sha256"],
            "criticReportSha256": critic_record["sha256"],
        },
    )
    state["updatedAt"] = utc_now()
    atomic_write_json(state_path, state)
    print(f"Recorded independent critic round {prospective_round_count}: {args.action}.")
    if state["status"] == "awaiting-correction":
        print(
            "Next: builder correct exactly highestImpactFinding.id="
            f"{report['highestImpactFinding']['id']}."
        )
    elif state["status"] == "complete":
        print("Pipeline complete.")
    elif state.get("currentPass"):
        print(f"Unlocked pass: {state['currentPass']}")
    return 0


def command_correct(args: argparse.Namespace) -> int:
    state_path, state = load_state(args.state)
    if state.get("status") != "awaiting-correction":
        raise ValueError("A correction can only be recorded while awaiting-correction")
    current_id = state.get("currentPass")
    if args.pass_id != current_id:
        raise ValueError(f"Only the current pass may be corrected: {current_id}")
    ensure_pinned_contract(state)
    current = pass_state(state, current_id)
    if current.get("builderId") != args.builder_id.strip():
        raise ValueError("Only the assigned builder may record the correction")
    rounds = current.get("criticRounds", [])
    corrections = current.get("corrections", [])
    if not rounds or len(corrections) >= len(rounds):
        raise ValueError("No uncorrected critic round exists")
    latest = rounds[-1]
    critic_id = latest["criticId"]
    if args.builder_id.strip() == critic_id:
        raise ValueError("The independent critic cannot act as the builder")
    expected_id = latest["report"]["highestImpactFinding"]["id"]
    if args.root_cause_id != expected_id:
        raise ValueError(
            f"Correction must target the single highest-impact root cause {expected_id}; "
            f"got {args.root_cause_id}"
        )
    changed = [item.strip() for item in args.changed if item.strip()]
    if not changed:
        raise ValueError("Record at least one exact Blender change with --changed")
    checkpoint = evidence_record(args.checkpoint)
    if Path(checkpoint["path"]).suffix.lower() != ".blend":
        raise ValueError("Correction checkpoint must be a .blend file")
    prior_checkpoint = latest.get("checkpoint")
    if prior_checkpoint and checkpoint["sha256"] == prior_checkpoint.get("sha256"):
        raise ValueError("Correction checkpoint must differ from the reviewed checkpoint")
    artifacts = [evidence_record(item) for item in args.artifact]
    correction = {
        "timestamp": utc_now(),
        "criticRound": latest["round"],
        "builderId": args.builder_id.strip(),
        "rootCauseId": args.root_cause_id,
        "summary": args.summary.strip(),
        "changed": changed,
        "checkpoint": checkpoint,
        "priorCheckpointSha256": (
            prior_checkpoint.get("sha256") if isinstance(prior_checkpoint, dict) else None
        ),
        "artifacts": artifacts,
    }
    if not correction["summary"]:
        raise ValueError("--summary must not be empty")
    corrections.append(correction)
    current["status"] = "unlocked"
    state["status"] = "active"
    append_transition(
        state,
        "scene-correction-recorded",
        {
            "passId": current_id,
            "criticRound": latest["round"],
            "builderId": args.builder_id.strip(),
            "rootCauseId": args.root_cause_id,
            "priorCheckpointSha256": correction["priorCheckpointSha256"],
            "checkpointSha256": checkpoint["sha256"],
        },
    )
    state["updatedAt"] = utc_now()
    atomic_write_json(state_path, state)
    print(f"Recorded correction for {args.root_cause_id}.")
    print("Next: rerender the same evidence roles and dispatch a fresh critic context.")
    return 0


def command_revise_spec(args: argparse.Namespace) -> int:
    state_path, state = load_state(args.state)
    if state.get("status") != "awaiting-spec-revision":
        raise ValueError("A spec revision requires awaiting-spec-revision state")
    current_id = state.get("currentPass")
    if args.pass_id != current_id:
        raise ValueError(f"Only the current pass may revise the spec: {current_id}")
    current = pass_state(state, current_id)
    if current.get("builderId") != args.builder_id.strip():
        raise ValueError("Only the assigned builder may record the spec revision")
    rounds = current.get("criticRounds", [])
    corrections = current.get("corrections", [])
    if not rounds or len(corrections) >= len(rounds):
        raise ValueError("No uncorrected refine-spec critic round exists")
    latest = rounds[-1]
    if latest.get("action") != "refine-spec":
        raise ValueError("Latest critic decision is not refine-spec")
    expected_id = latest["report"]["highestImpactFinding"]["id"]
    if args.root_cause_id != expected_id:
        raise ValueError(
            f"Spec revision must target highest-impact root cause {expected_id}"
        )
    spec_path = Path(args.spec).expanduser().resolve()
    if spec_path != Path(state["specPath"]).expanduser().resolve():
        raise ValueError("--spec must be the project's reconstruction-spec.json")
    errors, warnings = validate_spec(state)
    for warning in warnings:
        print(f"WARNING: {warning}")
    if errors:
        raise ValueError("Revised spec validation failed:\n- " + "\n- ".join(errors))
    revised_record = evidence_record(str(spec_path))
    revised_spec = read_json(spec_path)
    old_hash = state["approvedContract"]["sha256"]
    if revised_record["sha256"] == old_hash:
        raise ValueError("Revised spec must differ from the previously approved contract")
    reference_hashes = {
        item["id"]: item["sha256"] for item in revised_spec["references"]
    }
    if reference_hashes != state["approvedContract"]["referenceHashes"]:
        raise ValueError(
            "Spec revision cannot silently replace admitted references; "
            "request input and re-run intake instead"
        )
    state["approvedContract"] = {
        **revised_record,
        "referenceHashes": reference_hashes,
        "approvedAt": utc_now(),
        "supersedesSha256": old_hash,
    }
    revision = {
        "timestamp": utc_now(),
        "type": "spec-revision",
        "criticRound": latest["round"],
        "builderId": args.builder_id.strip(),
        "rootCauseId": args.root_cause_id,
        "summary": args.summary.strip(),
        "priorContractSha256": old_hash,
        "contractSha256": revised_record["sha256"],
    }
    if not revision["summary"]:
        raise ValueError("--summary must not be empty")
    corrections.append(revision)
    current["status"] = "unlocked"
    state["status"] = "active"
    append_transition(
        state,
        "spec-revision-approved",
        {
            "passId": current_id,
            "criticRound": latest["round"],
            "rootCauseId": args.root_cause_id,
            "priorContractSha256": old_hash,
            "contractSha256": revised_record["sha256"],
        },
    )
    state["updatedAt"] = utc_now()
    atomic_write_json(state_path, state)
    print(f"Recorded validated spec revision for {args.root_cause_id}.")
    return 0


def command_resume(args: argparse.Namespace) -> int:
    state_path, state = load_state(args.state)
    if state.get("status") != "waiting-input":
        raise ValueError("Only a waiting-input pipeline can be resumed")
    current_id = state.get("currentPass")
    current = pass_state(state, current_id)
    artifacts = [evidence_record(item) for item in args.artifact]
    if not artifacts:
        raise ValueError("Input resolution requires at least one --artifact")
    old_contract_hash = state["approvedContract"]["sha256"]
    current_spec_hash = sha256_file(Path(state["specPath"]))
    if current_spec_hash != old_contract_hash:
        errors, warnings = validate_spec(state)
        for warning in warnings:
            print(f"WARNING: {warning}")
        if errors:
            raise ValueError(
                "Input-updated spec validation failed:\n- " + "\n- ".join(errors)
            )
        revised_spec = read_json(Path(state["specPath"]))
        revised_record = evidence_record(state["specPath"])
        state["approvedContract"] = {
            **revised_record,
            "referenceHashes": {
                item["id"]: item["sha256"] for item in revised_spec["references"]
            },
            "approvedAt": utc_now(),
            "supersedesSha256": old_contract_hash,
        }
    current["status"] = "unlocked"
    resolution = {
        "timestamp": utc_now(),
        "type": "input-resolution",
        "note": args.note.strip(),
        "artifacts": artifacts,
        "priorContractSha256": old_contract_hash,
        "contractSha256": state["approvedContract"]["sha256"],
    }
    current.setdefault("resumeHistory", []).append(resolution)
    current.setdefault("corrections", []).append(resolution)
    state["status"] = "active"
    append_transition(
        state,
        "input-resolution-recorded",
        {
            "passId": current_id,
            "artifactHashes": [item["sha256"] for item in artifacts],
            "priorContractSha256": old_contract_hash,
            "contractSha256": state["approvedContract"]["sha256"],
        },
    )
    state["updatedAt"] = utc_now()
    atomic_write_json(state_path, state)
    print(f"Resumed pass: {current_id}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Manage an evidence-gated img2blender reconstruction pipeline."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser("init", help="Initialize a reconstruction project")
    init_parser.add_argument("--project-dir", required=True)
    init_parser.add_argument("--name", required=True)
    init_parser.add_argument("--reference", action="append", required=True)
    init_parser.add_argument("--target", default="hero-render")
    init_parser.add_argument("--task-mode", choices=sorted(TASK_MODES), default="faithful-reconstruction")
    init_parser.add_argument("--validation-scope", choices=sorted(VALIDATION_SCOPES), default="visual-asset")
    init_parser.add_argument("--complexity", choices=sorted(DETAIL_MINIMUMS), default="complex")
    init_parser.add_argument(
        "--subject-route", action="append", choices=sorted(SUBJECT_ROUTES), default=[]
    )
    init_parser.add_argument("--global-threshold", type=float, default=0.82)
    init_parser.add_argument("--critical-threshold", type=float, default=0.85)
    init_parser.add_argument("--max-critic-rounds", type=int, default=4)
    init_parser.add_argument("--plateau-delta", type=float, default=0.02)
    init_parser.set_defaults(handler=command_init)

    migrate_parser = subparsers.add_parser("migrate", help="Migrate a schema v1 project to v2")
    migrate_parser.add_argument("state")
    migrate_parser.set_defaults(handler=command_migrate)

    status_parser = subparsers.add_parser("status", help="Show the unlocked pass and evidence contract")
    status_parser.add_argument("state")
    status_parser.add_argument("--json", action="store_true")
    status_parser.set_defaults(handler=command_status)

    validate_parser = subparsers.add_parser("validate", help="Validate the reconstruction contract")
    validate_parser.add_argument("state")
    validate_parser.set_defaults(handler=command_validate)

    open_parser = subparsers.add_parser(
        "open-pass", help="Pin the builder and true start-of-pass checkpoint/baseline"
    )
    open_parser.add_argument("state")
    open_parser.add_argument("--pass-id", required=True)
    open_parser.add_argument("--builder-id", required=True)
    open_parser.add_argument("--start-checkpoint", required=True)
    open_parser.add_argument("--start-reference-render", required=True)
    open_parser.set_defaults(handler=command_open_pass)

    review_parser = subparsers.add_parser(
        "review", help="Record an independent critic round and route the pass"
    )
    review_parser.add_argument("state")
    review_parser.add_argument("--pass-id", required=True)
    review_parser.add_argument("--action", choices=sorted(ACTIONS), required=True)
    review_parser.add_argument("--summary", required=True)
    review_parser.add_argument("--builder-id", default="")
    review_parser.add_argument("--critic-report")
    review_parser.add_argument("--checkpoint")
    review_parser.add_argument("--render-manifest")
    review_parser.add_argument("--comparison-manifest")
    review_parser.add_argument("--render", action="append", default=[], metavar="ROLE=PATH")
    review_parser.add_argument(
        "--comparison", action="append", default=[], metavar="ROLE=PATH"
    )
    review_parser.add_argument("--artifact", action="append", default=[])
    review_parser.add_argument("--audit")
    review_parser.add_argument("--invariant-report")
    review_parser.set_defaults(handler=command_review)

    correct_parser = subparsers.add_parser(
        "correct", help="Record the builder's one-root-cause correction"
    )
    correct_parser.add_argument("state")
    correct_parser.add_argument("--pass-id", required=True)
    correct_parser.add_argument("--builder-id", required=True)
    correct_parser.add_argument("--root-cause-id", required=True)
    correct_parser.add_argument("--summary", required=True)
    correct_parser.add_argument("--changed", action="append", default=[])
    correct_parser.add_argument("--checkpoint", required=True)
    correct_parser.add_argument("--artifact", action="append", default=[])
    correct_parser.set_defaults(handler=command_correct)

    revise_parser = subparsers.add_parser(
        "revise-spec", help="Record a validated typed spec revision"
    )
    revise_parser.add_argument("state")
    revise_parser.add_argument("--pass-id", required=True)
    revise_parser.add_argument("--builder-id", required=True)
    revise_parser.add_argument("--root-cause-id", required=True)
    revise_parser.add_argument("--summary", required=True)
    revise_parser.add_argument("--spec", required=True)
    revise_parser.set_defaults(handler=command_revise_spec)

    resume_parser = subparsers.add_parser(
        "resume", help="Resume a pipeline after new input arrives"
    )
    resume_parser.add_argument("state")
    resume_parser.add_argument("--note", required=True)
    resume_parser.add_argument("--artifact", action="append", default=[])
    resume_parser.set_defaults(handler=command_resume)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    if hasattr(args, "global_threshold") and not 0 <= args.global_threshold <= 1:
        parser.error("--global-threshold must be from 0 to 1")
    if hasattr(args, "critical_threshold") and not 0 <= args.critical_threshold <= 1:
        parser.error("--critical-threshold must be from 0 to 1")
    if hasattr(args, "plateau_delta") and not 0 < args.plateau_delta <= 1:
        parser.error("--plateau-delta must be greater than 0 and at most 1")
    if hasattr(args, "max_critic_rounds") and not 2 <= args.max_critic_rounds <= 8:
        parser.error("--max-critic-rounds must be from 2 to 8")
    try:
        return int(args.handler(args))
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
