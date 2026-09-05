"""Measure explicit invariants in a saved Blender checkpoint.

blender --background checkpoint.blend --python check_geometry_invariants.py -- \
  --spec reconstruction-spec.json --pass-id secondary-form --out invariants.json

Dimensions use evaluated mesh vertices in the exact frame (object-local includes
modifier geometry but excludes the object's transform). Rotations in object-local
use the object's evaluated parent-relative matrix; named frames use relative world
matrices. Custom properties and sampled controls are numeric only. This script
restores sampled controls and never saves modifications to the checkpoint.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parent))
from geometry_invariants import (applicable_invariants, is_number, result_for,
                                 validate_invariants)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _object(bpy, name):
    obj = bpy.context.scene.objects.get(name)
    if obj is None:
        raise ValueError(f"exact scene object is missing: {name}")
    return obj


def _inverse(matrix, frame):
    if abs(matrix.determinant()) < 1e-12:
        raise ValueError(f"frame has a singular transform: {frame}")
    return matrix.inverted()


def measure(bpy, row):
    depsgraph = bpy.context.evaluated_depsgraph_get()
    objects = [_object(bpy, target) for target in row["targets"]]
    frame = row["frame"]
    frame_inverse = None
    if frame != "object-local":
        frame_inverse = _inverse(_object(bpy, frame).evaluated_get(depsgraph).matrix_world, frame)
    if row["kind"] == "count":
        return len(objects)
    values = {}
    for obj in objects:
        evaluated = obj.evaluated_get(depsgraph)
        if row["kind"] == "property":
            value = evaluated.get(row["property"])
            if not is_number(value):
                raise ValueError(f"{obj.name}: missing or nonnumeric custom property {row['property']}")
            values[obj.name] = value
        elif row["kind"] == "rotation":
            matrix = evaluated.matrix_local if frame_inverse is None else frame_inverse @ evaluated.matrix_world
            values[obj.name] = list(matrix.to_euler("XYZ"))
        else:
            if evaluated.type != "MESH":
                raise ValueError(f"{obj.name}: dimensions require an evaluated mesh")
            inverse = frame_inverse if frame_inverse is not None else _inverse(evaluated.matrix_world, obj.name)
            transform = inverse @ evaluated.matrix_world
            group_index = None
            if "vertexGroup" in row:
                group = evaluated.vertex_groups.get(row["vertexGroup"])
                if group is None:
                    raise ValueError(f"{obj.name}: vertex group {row['vertexGroup']} is missing")
                group_index = group.index
            mesh = evaluated.to_mesh(preserve_all_data_layers=True, depsgraph=depsgraph)
            try:
                vertices = [transform @ vertex.co for vertex in mesh.vertices
                            if group_index is None or any(g.group == group_index and g.weight > 0
                                                          for g in vertex.groups)]
                if len(vertices) < 2:
                    raise ValueError(f"{obj.name}: measurement requires at least two evaluated vertices")
                values[obj.name] = [max(v[axis] for v in vertices) - min(v[axis] for v in vertices)
                                    for axis in range(3)]
            finally:
                evaluated.to_mesh_clear()
    return values


def measure_samples(bpy, row):
    measurements = []
    for sample in row.get("samples", []):
        control = _object(bpy, sample["controlObject"])
        prop = sample["inputProperty"]
        original = control.get(prop)
        if not is_number(original):
            raise ValueError(f"{control.name}: sample control {prop} must be an existing numeric custom property")
        try:
            control[prop] = sample["inputValue"]
            control.update_tag()
            bpy.context.view_layer.update()
            measurements.append(measure(bpy, row))
        finally:
            control[prop] = original
            control.update_tag()
            bpy.context.view_layer.update()
    return measurements


def write_report(path, report):
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(report, handle, indent=2, allow_nan=False)
            handle.write("\n")
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def main():
    import bpy
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--spec", required=True, type=Path)
    parser.add_argument("--pass-id", required=True)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else [])
    checkpoint = Path(bpy.data.filepath)
    if not bpy.data.filepath or not checkpoint.is_file():
        raise ValueError("a saved .blend checkpoint must be loaded")
    if args.out.resolve() in {checkpoint.resolve(), args.spec.resolve()}:
        raise ValueError("report output must not overwrite the checkpoint or contract")
    spec = json.loads(args.spec.read_text(encoding="utf-8"))
    report = {"schemaVersion": 2, "checkpointSha256": sha256_file(checkpoint),
              "specSha256": sha256_file(args.spec), "passId": args.pass_id,
              "results": [], "errors": validate_invariants(spec)}
    if not report["errors"]:
        rows = applicable_invariants(spec, args.pass_id)
        if not rows:
            report["errors"].append("no applicable geometry invariants; empty evidence cannot pass")
        for row in rows:
            try:
                measured = measure(bpy, row)
                sampled = measure_samples(bpy, row) if "samples" in row else None
                result = result_for(row, measured, sampled)
                report["results"].append(result)
                if not result["pass"]:
                    report["errors"].append(f"invariant {row['id']} failed its declared expectation")
            except (ValueError, RuntimeError, TypeError) as error:
                report["errors"].append(f"invariant {row['id']}: {error}")
    if sha256_file(checkpoint) != report["checkpointSha256"] or sha256_file(args.spec) != report["specSha256"]:
        report["errors"].append("checkpoint or spec changed during invariant measurement")
    write_report(args.out, report)
    print(f"Geometry invariants: {len(report['results'])} measured, {len(report['errors'])} errors; {args.out}")
    if report["errors"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
