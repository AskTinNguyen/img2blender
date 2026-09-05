"""Strict, standard-library contract and evidence validation for geometry invariants.

Dimensions are spans of evaluated mesh vertices in the declared coordinate frame.
They establish size, not profile identity. Rotations are XYZ Euler angles in radians;
comparisons use componentwise absolute error, deliberately without modulo wrapping.
"""
from __future__ import annotations

import math
import re
from typing import Any

MEASUREMENTS = {"pane", "rough-opening", "visible-opening", "component", "rig"}
KINDS = {"dimensions", "count", "property", "rotation"}
VISUAL_PASSES = {
    "camera-match", "blockout", "primary-form", "secondary-form", "topology-uv",
    "materials", "lighting", "microdetail", "final-delivery",
}


def is_number(value: Any) -> bool:
    try:
        return type(value) in (int, float) and math.isfinite(value)
    except OverflowError:
        return False


def is_vector(value: Any) -> bool:
    return isinstance(value, list) and len(value) == 3 and all(is_number(v) for v in value)


def _text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def validate_invariants(spec: dict[str, Any]) -> list[str]:
    """Return contract errors; an absent geometryInvariants field is backward compatible."""
    if not isinstance(spec, dict):
        return ["spec must be an object"]
    rows = spec.get("geometryInvariants", [])
    if not isinstance(rows, list):
        return ["geometryInvariants must be a list"]
    errors: list[str] = []
    seen: set[str] = set()
    analysis = spec.get("referenceAnalysis", {})
    features = analysis.get("observedFeatures", []) if isinstance(analysis, dict) else []
    features = features if isinstance(features, list) else []
    feature_ids = {
        feature.get("id") for feature in features
        if isinstance(feature, dict) and isinstance(feature.get("id"), str)
    }
    for index, row in enumerate(rows):
        prefix = f"geometryInvariants[{index}]"
        if not isinstance(row, dict):
            errors.append(f"{prefix} must be an object")
            continue
        for field in ("id", "featureId", "frame"):
            if not _text(row.get(field)):
                errors.append(f"{prefix}.{field} must be a nonempty string")
        if _text(row.get("id")):
            if row["id"] in seen:
                errors.append(f"{prefix}.id is duplicated")
            seen.add(row["id"])
        if not isinstance(row.get("featureId"), str) or row["featureId"] not in feature_ids:
            errors.append(f"{prefix}.featureId must identify an observed feature")
        measurement, kind = row.get("measurement"), row.get("kind")
        if not isinstance(measurement, str) or measurement not in MEASUREMENTS:
            errors.append(f"{prefix}.measurement is unsupported")
        if not isinstance(kind, str) or kind not in KINDS:
            errors.append(f"{prefix}.kind is unsupported")
        kind = kind if isinstance(kind, str) else ""
        measurement = measurement if isinstance(measurement, str) else ""
        targets = row.get("targets")
        if (not isinstance(targets, list) or not targets or
                not all(_text(target) for target in targets) or
                len(set(targets)) != len(targets)):
            errors.append(f"{prefix}.targets must be nonempty, unique exact object names")
        tolerance = row.get("tolerance")
        if not is_number(tolerance) or tolerance < 0:
            errors.append(f"{prefix}.tolerance must be a finite nonnegative number")
        expected = row.get("expected")
        if kind in {"dimensions", "rotation"}:
            if not is_vector(expected):
                errors.append(f"{prefix}.expected must contain three finite numbers")
            elif kind == "dimensions" and any(value < 0 for value in expected):
                errors.append(f"{prefix}.expected dimensions cannot be negative")
        elif kind == "count":
            if type(expected) is not int or expected < 1:
                errors.append(f"{prefix}.expected must be a positive integer")
            if isinstance(targets, list) and expected != len(targets):
                errors.append(f"{prefix}.expected count must equal the number of exact targets")
            if tolerance != 0:
                errors.append(f"{prefix}.count tolerance must be zero")
        elif kind == "property":
            if not is_number(expected):
                errors.append(f"{prefix}.expected must be finite numeric property value")
            if not _text(row.get("property")):
                errors.append(f"{prefix}.property must name an exact numeric custom property")
        if measurement in {"rough-opening", "visible-opening"} and kind == "dimensions":
            if not _text(row.get("vertexGroup")):
                errors.append(f"{prefix}.vertexGroup must identify actual opening boundary vertices")
        if "vertexGroup" in row and (kind != "dimensions" or not _text(row["vertexGroup"])):
            errors.append(f"{prefix}.vertexGroup is supported only for dimensions")
        if "applicablePasses" in row:
            passes = row["applicablePasses"]
            if (not isinstance(passes, list) or not passes or
                    not all(isinstance(p, str) and p in VISUAL_PASSES for p in passes) or
                    len(set(passes)) != len(passes)):
                errors.append(f"{prefix}.applicablePasses must contain unique visual pass IDs")
        if "samples" in row:
            samples = row["samples"]
            if kind != "rotation" or not isinstance(samples, list) or not samples:
                errors.append(f"{prefix}.samples requires a nonempty rotation sample list")
            else:
                seen_samples = set()
                for sample in samples:
                    if (not isinstance(sample, dict) or
                            not _text(sample.get("controlObject")) or
                            not _text(sample.get("inputProperty")) or
                            not is_number(sample.get("inputValue")) or
                            not is_vector(sample.get("expected"))):
                        errors.append(f"{prefix}.samples must define controlObject, inputProperty, finite inputValue and expected radians")
                        continue
                    key = (sample["controlObject"], sample["inputProperty"], sample["inputValue"])
                    if key in seen_samples:
                        errors.append(f"{prefix}.samples contains duplicate input samples")
                    seen_samples.add(key)
    return errors


def applicable_invariants(spec: dict[str, Any], pass_id: str) -> list[dict[str, Any]]:
    if pass_id not in VISUAL_PASSES:
        return []
    return [row for row in spec.get("geometryInvariants", [])
            if pass_id == "final-delivery" or pass_id in row.get("applicablePasses", VISUAL_PASSES)]


def _matches(value: Any, expected: Any, tolerance: float) -> bool:
    if isinstance(expected, list):
        return is_vector(value) and all(abs(a - b) <= tolerance for a, b in zip(value, expected))
    return is_number(value) and abs(value - expected) <= tolerance


def evaluate_invariant(row: dict[str, Any], measured: Any) -> bool:
    """Compare every target against the declared absolute expectation, never peer equality."""
    if row["kind"] == "count":
        return type(measured) is int and measured == row["expected"]
    if not isinstance(measured, dict) or set(measured) != set(row["targets"]):
        return False
    return all(_matches(value, row["expected"], row["tolerance"]) for value in measured.values())


def result_for(row: dict[str, Any], measured: Any, sampled: Any = None) -> dict[str, Any]:
    result = {"id": row["id"], "measurement": row["measurement"],
              "expected": row["expected"], "measured": measured,
              "pass": evaluate_invariant(row, measured)}
    if "samples" in row:
        result["sampled"] = sampled
        result["pass"] = result["pass"] and _samples_pass(row, sampled)
    return result


def _samples_pass(row: dict[str, Any], sampled: Any) -> bool:
    if not isinstance(sampled, list) or len(sampled) != len(row["samples"]):
        return False
    return all(evaluate_invariant({**row, "expected": sample["expected"]}, value)
               for sample, value in zip(row["samples"], sampled))


def _valid_measurement(row: dict[str, Any], measured: Any) -> bool:
    if row["kind"] == "count":
        return type(measured) is int and measured >= 0
    if not isinstance(measured, dict) or set(measured) != set(row["targets"]):
        return False
    if row["kind"] == "property":
        return all(is_number(value) for value in measured.values())
    return all(is_vector(value) and (row["kind"] != "dimensions" or all(v >= 0 for v in value))
               for value in measured.values())


def validate_invariant_report(report: dict[str, Any], spec: dict[str, Any],
                              checkpoint_hash: str, spec_hash: str, pass_id: str,
                              require_pass: bool = True) -> None:
    """Recompute evidence; require success by default.

    With require_pass=False, complete finite failed measurements may be recorded for
    refinement/stop. Missing measurements and unsupported adapter errors still fail.
    """
    errors = validate_invariants(spec)
    if errors:
        raise ValueError("; ".join(errors))
    if not isinstance(report, dict) or type(report.get("schemaVersion")) is not int or report["schemaVersion"] != 2:
        raise ValueError("invariant report schemaVersion must be 2")
    for field, expected in (("checkpointSha256", checkpoint_hash), ("specSha256", spec_hash)):
        if not isinstance(expected, str) or not re.fullmatch(r"[0-9a-f]{64}", expected) or report.get(field) != expected:
            raise ValueError(f"invariant report {field} is missing or stale")
    if report.get("passId") != pass_id:
        raise ValueError("invariant report passId mismatch")
    report_errors = report.get("errors")
    if (not isinstance(report_errors, list) or
            any(not isinstance(error, str) for error in report_errors) or
            (require_pass and report_errors)):
        raise ValueError("invariant report contains errors or lacks errors list")
    rows = applicable_invariants(spec, pass_id)
    results = report.get("results")
    if not rows or not isinstance(results, list) or not results:
        raise ValueError("invariant report must contain nonempty applicable results")
    by_id = {}
    for result in results:
        if not isinstance(result, dict) or not _text(result.get("id")) or result["id"] in by_id:
            raise ValueError("invariant report has malformed or duplicate result IDs")
        by_id[result["id"]] = result
    if set(by_id) != {row["id"] for row in rows}:
        raise ValueError("invariant report must contain every applicable invariant exactly once")
    failed_messages = set()
    for row in rows:
        result = by_id[row["id"]]
        if (result.get("measurement") != row["measurement"] or
                not _matches(result.get("expected"), row["expected"], 0)):
            raise ValueError(f"invariant {row['id']} expectation or measurement mismatch")
        if not _valid_measurement(row, result.get("measured")):
            raise ValueError(f"invariant {row['id']} has malformed measured values")
        if "samples" in row:
            sampled = result.get("sampled")
            if (not isinstance(sampled, list) or len(sampled) != len(row["samples"]) or
                    not all(_valid_measurement(row, value) for value in sampled)):
                raise ValueError(f"invariant {row['id']} has malformed sampled values")
        passed = evaluate_invariant(row, result["measured"]) and (
            "samples" not in row or _samples_pass(row, result["sampled"]))
        if result.get("pass") is not passed or (require_pass and not passed):
            raise ValueError(f"invariant {row['id']} failed its declared expectation or misreported pass")
        if not passed:
            failed_messages.add(f"invariant {row['id']} failed its declared expectation")
    if len(set(report_errors)) != len(report_errors) or set(report_errors) - failed_messages:
        raise ValueError("invariant report contains measurement errors unsupported by complete numeric results")
