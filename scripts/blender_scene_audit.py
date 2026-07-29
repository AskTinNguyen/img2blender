"""Audit a Blender reconstruction scene.

Run inside Blender:
  blender --background scene.blend --python blender_scene_audit.py -- \
    --out scene-audit.json --stage working --strict
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import math
import os
import re
import sys
import tempfile
from pathlib import Path
from typing import Any

import bmesh
import bpy


GENERIC_NAME = re.compile(
    r"^(Cube|Sphere|Icosphere|Cylinder|Cone|Plane|Torus|Suzanne|BezierCurve|Curve|Text)"
    r"(?:\.\d+)?$",
    re.IGNORECASE,
)
MODEL_COLLECTIONS = {"MODEL_SOURCE", "MODEL_FINAL", "DETAIL", "EXPORT"}
IGNORE_COLLECTIONS = {"REF"}


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit an img2blender scene")
    parser.add_argument("--out", required=True)
    parser.add_argument("--stage", choices=("working", "final"), default="working")
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--allow-realtime", action="store_true")
    parser.add_argument("--min-resolution", type=int)
    parser.add_argument("--min-samples", type=int)
    parser.add_argument(
        "--required-role",
        action="append",
        default=[],
        help="Require an exact img2blender_role camera tag.",
    )
    argv = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    return parser.parse_args(argv)


def collection_names(obj: bpy.types.Object) -> set[str]:
    return {collection.name for collection in obj.users_collection}


def select_model_objects(stage: str) -> list[bpy.types.Object]:
    mesh_objects = [
        obj
        for obj in bpy.context.scene.objects
        if obj.type == "MESH"
        and (
            stage == "final"
            or not obj.get("img2blender_ignore_audit", False)
        )
    ]
    if stage == "final":
        return [
            obj
            for obj in mesh_objects
            if not collection_names(obj).intersection(IGNORE_COLLECTIONS)
        ]
    explicitly_scoped = [
        obj
        for obj in mesh_objects
        if obj.get("img2blender_component_id")
        or collection_names(obj).intersection(MODEL_COLLECTIONS)
    ]
    if explicitly_scoped:
        return explicitly_scoped
    return [
        obj
        for obj in mesh_objects
        if not collection_names(obj).intersection(IGNORE_COLLECTIONS)
    ]


def upstream_images(
    socket: bpy.types.NodeSocket, visited_nodes: set[int] | None = None
) -> set[str]:
    visited_nodes = visited_nodes or set()
    result: set[str] = set()
    for link in socket.links:
        node = link.from_node
        pointer = node.as_pointer()
        if pointer in visited_nodes:
            continue
        visited_nodes.add(pointer)
        if node.type == "TEX_IMAGE" and getattr(node, "image", None):
            result.add(node.image.name)
            continue
        for input_socket in getattr(node, "inputs", []):
            if input_socket.is_linked:
                result.update(upstream_images(input_socket, visited_nodes))
    return result


def material_record(material: bpy.types.Material) -> dict[str, Any]:
    has_node_tree = material.node_tree is not None
    record: dict[str, Any] = {
        "name": material.name,
        "usesNodes": has_node_tree,
        "principledCount": 0,
        "hasMaterialOutput": False,
        "imageUsage": {},
        "issues": [],
    }
    if not has_node_tree:
        record["issues"].append(
            {
                "severity": "warning",
                "code": "material-without-nodes",
                "message": "Material does not use a node tree.",
            }
        )
        return record

    nodes = material.node_tree.nodes
    record["hasMaterialOutput"] = any(node.type == "OUTPUT_MATERIAL" for node in nodes)
    principled_nodes = [node for node in nodes if node.type == "BSDF_PRINCIPLED"]
    record["principledCount"] = len(principled_nodes)
    if not record["hasMaterialOutput"]:
        record["issues"].append(
            {
                "severity": "error",
                "code": "missing-material-output",
                "message": "Node material has no Material Output node.",
            }
        )
    if not principled_nodes:
        record["issues"].append(
            {
                "severity": "warning",
                "code": "no-principled-bsdf",
                "message": "No Principled BSDF was found; verify the custom shader deliberately.",
            }
        )
        return record

    tracked_inputs = (
        "Base Color",
        "Metallic",
        "Roughness",
        "Normal",
        "Alpha",
        "Emission Color",
    )
    image_to_inputs: dict[str, set[str]] = {}
    for node in principled_nodes:
        for input_name in tracked_inputs:
            socket = node.inputs.get(input_name)
            if not socket or not socket.is_linked:
                continue
            images = upstream_images(socket)
            if images:
                record["imageUsage"].setdefault(input_name, [])
                record["imageUsage"][input_name].extend(sorted(images))
            for image_name in images:
                image_to_inputs.setdefault(image_name, set()).add(input_name)

    if not material.get("img2blender_allow_packed_maps", False):
        for image_name, inputs in image_to_inputs.items():
            physically_unrelated = {"Base Color", "Roughness", "Metallic", "Normal"}.intersection(
                inputs
            )
            if "Base Color" in physically_unrelated and len(physically_unrelated) > 1:
                record["issues"].append(
                    {
                        "severity": "warning",
                        "code": "shared-pbr-image",
                        "message": (
                            f"Image {image_name!r} feeds Base Color and "
                            f"{sorted(physically_unrelated - {'Base Color'})}; "
                            "verify channel decoding and color space."
                        ),
                    }
                )
    return record


def mesh_record(obj: bpy.types.Object) -> dict[str, Any]:
    mesh = obj.data
    bm = bmesh.new()
    bm.from_mesh(mesh)
    bm.verts.ensure_lookup_table()
    bm.edges.ensure_lookup_table()
    bm.faces.ensure_lookup_table()

    loose_vertices = sum(1 for vertex in bm.verts if not vertex.link_edges)
    loose_edges = sum(1 for edge in bm.edges if not edge.link_faces)
    boundary_edges = sum(1 for edge in bm.edges if len(edge.link_faces) == 1)
    multi_face_edges = sum(1 for edge in bm.edges if len(edge.link_faces) > 2)
    degenerate_faces = sum(1 for face in bm.faces if face.calc_area() <= 1e-12)
    triangles = sum(1 for face in bm.faces if len(face.verts) == 3)
    quads = sum(1 for face in bm.faces if len(face.verts) == 4)
    ngons = sum(1 for face in bm.faces if len(face.verts) > 4)
    bm.free()

    component_id = obj.get("img2blender_component_id")
    scale = tuple(float(value) for value in obj.scale)
    dimensions = tuple(float(value) for value in obj.dimensions)
    materials = [
        slot.material.name if slot.material else None for slot in obj.material_slots
    ]
    record: dict[str, Any] = {
        "name": obj.name,
        "dataName": mesh.name,
        "componentId": component_id,
        "attachmentTo": obj.get("img2blender_attachment_to"),
        "contactVerified": obj.get("img2blender_contact_verified"),
        "collections": sorted(collection_names(obj)),
        "vertices": len(mesh.vertices),
        "edges": len(mesh.edges),
        "polygons": len(mesh.polygons),
        "triangles": triangles,
        "quads": quads,
        "ngons": ngons,
        "looseVertices": loose_vertices,
        "looseEdges": loose_edges,
        "boundaryEdges": boundary_edges,
        "multiFaceEdges": multi_face_edges,
        "degenerateFaces": degenerate_faces,
        "uvLayers": [layer.name for layer in mesh.uv_layers],
        "materialSlots": materials,
        "scale": scale,
        "dimensions": dimensions,
        "modifiers": [
            {"name": modifier.name, "type": modifier.type}
            for modifier in obj.modifiers
        ],
        "issues": [],
    }

    issues = record["issues"]
    if GENERIC_NAME.match(obj.name):
        issues.append(
            {
                "severity": "error",
                "code": "generic-object-name",
                "message": "Object still has a generic primitive name.",
            }
        )
    if not component_id:
        issues.append(
            {
                "severity": "warning",
                "code": "missing-component-id",
                "message": "Set img2blender_component_id to link the mesh to the spec.",
            }
        )
    if obj.get("img2blender_requires_attachment", False):
        if not obj.get("img2blender_attachment_to"):
            issues.append(
                {
                    "severity": "error",
                    "code": "missing-attachment-target",
                    "message": (
                        "Object requires attachment but has no "
                        "img2blender_attachment_to component id."
                    ),
                }
            )
        if obj.get("img2blender_contact_verified") is not True:
            issues.append(
                {
                    "severity": "error",
                    "code": "unverified-attachment-contact",
                    "message": (
                        "Object attachment contact has not been explicitly verified."
                    ),
                }
            )
    exception_flags = (
        "img2blender_allow_open",
        "img2blender_uv_not_required",
        "img2blender_allow_nonunit_scale",
        "img2blender_ignore_audit",
    )
    if any(obj.get(flag, False) for flag in exception_flags) and not str(
        obj.get("img2blender_exception_reason", "")
    ).strip():
        issues.append(
            {
                "severity": "error",
                "code": "undocumented-audit-exception",
                "message": (
                    "Intentional audit exceptions require "
                    "img2blender_exception_reason."
                ),
            }
        )
    if obj.get("img2blender_ignore_audit", False):
        issues.append(
            {
                "severity": "error",
                "code": "audit-ignore-forbidden-in-scope",
                "message": (
                    "An in-scope final mesh cannot be excluded from audit; move true "
                    "reference-only geometry to REF or remove the ignore flag."
                ),
            }
        )
    if any(value < 0 for value in scale):
        issues.append(
            {
                "severity": "error",
                "code": "negative-scale",
                "message": "Negative object scale can invert normals and break baking/export.",
            }
        )
    if (
        any(abs(value - 1.0) > 1e-4 for value in scale)
        and not obj.get("img2blender_allow_nonunit_scale", False)
    ):
        issues.append(
            {
                "severity": "warning",
                "code": "nonunit-scale",
                "message": "Apply or document non-unit scale before scale-sensitive operations.",
            }
        )
    if mesh.polygons and not materials:
        issues.append(
            {
                "severity": "error",
                "code": "missing-material",
                "message": "Mesh has faces but no material slots.",
            }
        )
    if any(material is None for material in materials):
        issues.append(
            {
                "severity": "error",
                "code": "empty-material-slot",
                "message": "One or more material slots are empty.",
            }
        )
    if (
        mesh.polygons
        and not mesh.uv_layers
        and not obj.get("img2blender_uv_not_required", False)
    ):
        issues.append(
            {
                "severity": "warning",
                "code": "missing-uv",
                "message": "Mesh has no UV layer; document why UVs are unnecessary.",
            }
        )
    if loose_vertices or loose_edges:
        issues.append(
            {
                "severity": "error",
                "code": "loose-geometry",
                "message": (
                    f"Found {loose_vertices} loose vertex/vertices and "
                    f"{loose_edges} loose edge(s)."
                ),
            }
        )
    if degenerate_faces:
        issues.append(
            {
                "severity": "error",
                "code": "degenerate-faces",
                "message": f"Found {degenerate_faces} near-zero-area face(s).",
            }
        )
    if multi_face_edges:
        issues.append(
            {
                "severity": "error",
                "code": "nonmanifold-multiface-edge",
                "message": f"Found {multi_face_edges} edge(s) shared by more than two faces.",
            }
        )
    if (
        boundary_edges
        and not obj.get("img2blender_allow_open", False)
    ):
        issues.append(
            {
                "severity": "warning",
                "code": "open-boundary",
                "message": (
                    f"Found {boundary_edges} boundary edge(s); set "
                    "img2blender_allow_open only when intentional."
                ),
            }
        )
    if mesh.vertices and min(dimensions) <= 1e-9:
        issues.append(
            {
                "severity": "warning",
                "code": "zero-thickness-axis",
                "message": "Object has a near-zero bounding-box dimension.",
            }
        )
    return record


def camera_role(camera: bpy.types.Object) -> str | None:
    explicit = camera.get("img2blender_role")
    if explicit:
        return str(explicit).lower()
    name = camera.name.upper()
    if "REFERENCE" in name:
        return "reference"
    if "ORBIT_LEFT" in name or "3Q_LEFT" in name:
        return "orbit-left"
    if "ORBIT_RIGHT" in name or "3Q_RIGHT" in name:
        return "orbit-right"
    if "BACK" in name:
        return "back"
    if "GRAZING" in name:
        return "grazing"
    if "NEUTRAL" in name:
        return "neutral"
    return None


def run_audit(args: argparse.Namespace) -> dict[str, Any]:
    scene = bpy.context.scene
    stage = args.stage
    minimum_resolution = args.min_resolution or (2048 if stage == "final" else 1024)
    minimum_samples = args.min_samples or (256 if stage == "final" else 64)
    issues: list[dict[str, Any]] = []

    def add_issue(
        severity: str,
        code: str,
        message: str,
        subject: str | None = None,
    ) -> None:
        record = {"severity": severity, "code": code, "message": message}
        if subject:
            record["subject"] = subject
        issues.append(record)

    mesh_records = [mesh_record(obj) for obj in select_model_objects(stage)]
    if not mesh_records:
        add_issue("error", "no-model-meshes", "No model mesh objects were found.")
    for record in mesh_records:
        for issue in record["issues"]:
            severity = issue["severity"]
            if stage == "working" and issue["code"] in {
                "generic-object-name",
                "missing-material",
                "empty-material-slot",
            }:
                severity = "warning"
            add_issue(severity, issue["code"], issue["message"], record["name"])
    component_ids = [
        record["componentId"] for record in mesh_records if record.get("componentId")
    ]
    for component_id in sorted(
        {value for value in component_ids if component_ids.count(value) > 1}
    ):
        add_issue(
            "error",
            "duplicate-component-id",
            f"Multiple mesh objects use component id {component_id!r}.",
            component_id,
        )
    component_id_set = set(component_ids)
    for record in mesh_records:
        target = record.get("attachmentTo")
        if target and target not in component_id_set:
            add_issue(
                "error",
                "unknown-attachment-target",
                f"Attachment target {target!r} does not exist in audited model components.",
                record["name"],
            )

    material_names = sorted(
        {
            material_name
            for record in mesh_records
            for material_name in record["materialSlots"]
            if material_name
        }
    )
    material_records = [
        material_record(bpy.data.materials[name])
        for name in material_names
        if name in bpy.data.materials
    ]
    for record in material_records:
        for issue in record["issues"]:
            severity = issue["severity"]
            if stage == "working" and issue["code"] == "missing-material-output":
                severity = "warning"
            add_issue(severity, issue["code"], issue["message"], record["name"])

    cameras = [obj for obj in scene.objects if obj.type == "CAMERA"]
    camera_records = [
        {
            "name": camera.name,
            "role": camera_role(camera),
            "lens": float(camera.data.lens),
            "type": camera.data.type,
        }
        for camera in cameras
    ]
    roles = {record["role"] for record in camera_records if record["role"]}
    if scene.camera is None:
        add_issue("error", "missing-active-camera", "Scene has no active camera.")
    if "reference-match" not in roles and "reference" not in roles:
        add_issue(
            "error" if stage == "final" else "warning",
            "missing-reference-camera",
            "No camera is tagged or named as the reference camera.",
        )
    orbit_roles = {"orbit-left", "orbit-right", "back"}.intersection(roles)
    if len(orbit_roles) < 2:
        add_issue(
            "error" if stage == "final" else "warning",
            "insufficient-orbit-cameras",
            "At least two meaningful orbit review cameras are required.",
        )
    for required_role in sorted(set(args.required_role)):
        if required_role not in roles:
            add_issue(
                "error",
                "missing-required-review-camera",
                f"No camera is tagged with required role {required_role!r}.",
                required_role,
            )

    render = scene.render
    effective_x = int(render.resolution_x * render.resolution_percentage / 100)
    effective_y = int(render.resolution_y * render.resolution_percentage / 100)
    if min(effective_x, effective_y) < minimum_resolution:
        add_issue(
            "error" if stage == "final" else "warning",
            "low-render-resolution",
            (
                f"Effective resolution {effective_x}×{effective_y} is below the "
                f"{minimum_resolution}px minimum on the short edge."
            ),
        )
    engine = scene.render.engine
    if stage == "final" and engine != "CYCLES" and not args.allow_realtime:
        add_issue(
            "error",
            "noncycles-final",
            "Final audit expects Cycles unless --allow-realtime is explicitly set.",
        )

    samples: int | None = None
    denoise: bool | None = None
    if engine == "CYCLES":
        samples = int(scene.cycles.samples)
        denoise = bool(getattr(scene.cycles, "use_denoising", False))
        if samples < minimum_samples:
            add_issue(
                "error" if stage == "final" else "warning",
                "low-cycle-samples",
                f"Cycles samples {samples} are below the {minimum_samples} target.",
            )

    lights = [obj for obj in scene.objects if obj.type == "LIGHT"]
    world_strength = None
    if scene.world and scene.world.node_tree:
        for node in scene.world.node_tree.nodes:
            if node.type == "BACKGROUND":
                world_strength = float(node.inputs["Strength"].default_value)
                break
    if not lights and not world_strength:
        add_issue(
            "warning",
            "no-lighting",
            "No lights or non-zero world background strength were detected.",
        )

    errors = sum(1 for issue in issues if issue["severity"] == "error")
    warnings = sum(1 for issue in issues if issue["severity"] == "warning")
    blend_path = Path(bpy.data.filepath).resolve() if bpy.data.filepath else None
    return {
        "schemaVersion": 2,
        "generatedAt": utc_now(),
        "blenderVersion": bpy.app.version_string,
        "blendFile": str(blend_path) if blend_path else None,
        "blendSha256": (
            sha256_file(blend_path) if blend_path and blend_path.is_file() else None
        ),
        "stage": stage,
        "strict": bool(args.strict),
        "scene": scene.name,
        "summary": {
            "status": "pass" if errors == 0 else "fail",
            "errors": errors,
            "warnings": warnings,
            "meshObjects": len(mesh_records),
            "materials": len(material_records),
            "cameras": len(camera_records),
            "lights": len(lights),
        },
        "renderSettings": {
            "engine": engine,
            "resolution": [effective_x, effective_y],
            "resolutionPercentage": int(render.resolution_percentage),
            "samples": samples,
            "denoise": denoise,
            "viewTransform": getattr(scene.view_settings, "view_transform", None),
            "look": getattr(scene.view_settings, "look", None),
            "displayDevice": getattr(scene.display_settings, "display_device", None),
            "exposure": float(scene.view_settings.exposure),
            "worldStrength": world_strength,
        },
        "cameras": camera_records,
        "meshes": mesh_records,
        "materials": material_records,
        "issues": issues,
    }


def main() -> int:
    args = parse_args()
    report = run_audit(args)
    output_path = Path(args.out).expanduser().resolve()
    atomic_write_json(output_path, report)
    summary = report["summary"]
    print(f"Scene audit: {summary['status']}")
    print(f"Errors: {summary['errors']}; warnings: {summary['warnings']}")
    print(f"Report: {output_path}")
    if args.strict and summary["errors"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
