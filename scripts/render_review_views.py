"""Render deterministic named review cameras from a Blender file.

Run inside Blender:
  blender --background scene.blend --python render_review_views.py -- \
    --out-dir renders/pass --all-tagged --required-role reference-match
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import re
import sys
import tempfile
from pathlib import Path
from typing import Any

import bpy


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
    parser = argparse.ArgumentParser(description="Render img2blender review cameras")
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--camera", action="append", default=[])
    parser.add_argument("--all-tagged", action="store_true")
    parser.add_argument(
        "--required-role",
        action="append",
        default=[],
        help="Fail unless a selected camera has this exact img2blender_role.",
    )
    parser.add_argument(
        "--engine",
        choices=(
            "CYCLES",
            "BLENDER_EEVEE",
            "BLENDER_EEVEE_NEXT",
            "BLENDER_WORKBENCH",
        ),
    )
    parser.add_argument("--samples", type=int)
    parser.add_argument("--resolution-x", type=int)
    parser.add_argument("--resolution-y", type=int)
    parser.add_argument("--resolution-percentage", type=int, default=100)
    parser.add_argument("--manifest-name", default="render-manifest.json")
    parser.add_argument("--seed", type=int, default=230519)
    argv = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    return parser.parse_args(argv)


def safe_filename(value: str) -> str:
    normalized = re.sub(r"[^A-Za-z0-9._-]+", "_", value.strip())
    return normalized.strip("._") or "camera"


def canonical_role(value: str) -> str:
    return value.strip().lower()


def role_for(camera: bpy.types.Object) -> str | None:
    role = camera.get("img2blender_role")
    return canonical_role(str(role)) if role else None


def role_state(scene: bpy.types.Scene, camera: bpy.types.Object) -> dict[str, Any]:
    role = role_for(camera)
    view_layer_name = str(
        camera.get("img2blender_view_layer", bpy.context.view_layer.name)
    )
    view_layer = scene.view_layers.get(view_layer_name)
    if view_layer is None:
        raise ValueError(
            f"Camera {camera.name} requests missing view layer {view_layer_name!r}"
        )
    light_rig = camera.get("img2blender_light_rig")
    material_override = (
        view_layer.material_override.name if view_layer.material_override else None
    )
    if role == "clay-silhouette" and not material_override:
        raise ValueError(
            f"Camera {camera.name} role clay-silhouette requires a view-layer material override"
        )
    if role == "neutral-material" and light_rig != "neutral":
        raise ValueError(
            f"Camera {camera.name} role neutral-material requires "
            "img2blender_light_rig='neutral'"
        )
    if role == "grazing-light" and light_rig != "grazing":
        raise ValueError(
            f"Camera {camera.name} role grazing-light requires "
            "img2blender_light_rig='grazing'"
        )
    if role and role.startswith("ortho-") and camera.data.type != "ORTHO":
        raise ValueError(f"Camera {camera.name} role {role} must be orthographic")
    return {
        "viewLayer": view_layer_name,
        "materialOverride": material_override,
        "lightRig": str(light_rig) if light_rig else None,
        "sceneVariant": camera.get("img2blender_scene_variant"),
    }


def select_cameras(args: argparse.Namespace) -> list[bpy.types.Object]:
    selected: list[bpy.types.Object] = []
    seen: set[str] = set()
    for name in args.camera:
        obj = bpy.data.objects.get(name)
        if not obj or obj.type != "CAMERA":
            raise ValueError(f"Camera does not exist: {name}")
        if obj.name not in seen:
            selected.append(obj)
            seen.add(obj.name)
    if args.all_tagged:
        tagged = sorted(
            (
                obj
                for obj in bpy.context.scene.objects
                if obj.type == "CAMERA" and obj.get("img2blender_role")
            ),
            key=lambda item: item.name,
        )
        for obj in tagged:
            if obj.name not in seen:
                selected.append(obj)
                seen.add(obj.name)
    if not selected:
        raise ValueError("Specify --camera at least once or use --all-tagged")
    return selected


def resolve_engine(scene: bpy.types.Scene, requested: str | None) -> str | None:
    if requested is None:
        return None
    engine_property = scene.render.bl_rna.properties.get("engine")
    available = (
        {item.identifier for item in engine_property.enum_items}
        if engine_property is not None
        else {scene.render.engine}
    )
    if requested in available:
        return requested
    aliases = {
        "BLENDER_EEVEE_NEXT": "BLENDER_EEVEE",
        "BLENDER_EEVEE": "BLENDER_EEVEE_NEXT",
    }
    alias = aliases.get(requested)
    if alias in available:
        print(f"Using engine alias {alias} for requested {requested}")
        return alias
    raise ValueError(
        f"Render engine {requested} is unavailable; available engines: {sorted(available)}"
    )


def main() -> int:
    args = parse_args()
    if args.samples is not None and args.samples < 1:
        raise ValueError("--samples must be positive")
    if not 1 <= args.resolution_percentage <= 100:
        raise ValueError("--resolution-percentage must be from 1 to 100")

    output_dir = Path(args.out_dir).expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    scene = bpy.context.scene
    cameras = select_cameras(args)
    camera_roles = [role_for(camera) for camera in cameras]
    duplicate_roles = sorted(
        {role for role in camera_roles if role and camera_roles.count(role) > 1}
    )
    if duplicate_roles:
        raise ValueError(f"Selected cameras have duplicate review roles: {duplicate_roles}")
    required_roles = {canonical_role(role) for role in args.required_role}
    missing_roles = sorted(required_roles - {role for role in camera_roles if role})
    if missing_roles:
        raise ValueError(f"Selected cameras are missing required roles: {missing_roles}")
    resolved_engine = resolve_engine(scene, args.engine)

    original = {
        "camera": scene.camera,
        "engine": scene.render.engine,
        "filepath": scene.render.filepath,
        "format": scene.render.image_settings.file_format,
        "resolution_x": scene.render.resolution_x,
        "resolution_y": scene.render.resolution_y,
        "resolution_percentage": scene.render.resolution_percentage,
        "samples": int(scene.cycles.samples) if hasattr(scene, "cycles") else None,
        "seed": int(scene.cycles.seed) if hasattr(scene, "cycles") else None,
    }

    if resolved_engine:
        scene.render.engine = resolved_engine
    if args.samples is not None and scene.render.engine == "CYCLES":
        scene.cycles.samples = args.samples
    if hasattr(scene, "cycles"):
        scene.cycles.seed = args.seed
    if args.resolution_x is not None:
        scene.render.resolution_x = args.resolution_x
    if args.resolution_y is not None:
        scene.render.resolution_y = args.resolution_y
    scene.render.resolution_percentage = args.resolution_percentage
    scene.render.image_settings.file_format = "PNG"

    rendered: list[dict[str, Any]] = []
    try:
        for camera in cameras:
            scene.camera = camera
            state = role_state(scene, camera)
            output_path = output_dir / f"{safe_filename(camera.name)}.png"
            scene.render.filepath = str(output_path)
            print(f"Rendering {camera.name} -> {output_path}")
            bpy.ops.render.render(write_still=True, layer=state["viewLayer"])
            if not output_path.is_file():
                raise RuntimeError(f"Blender did not write expected render: {output_path}")
            rendered.append(
                {
                    "camera": camera.name,
                    "role": role_for(camera),
                    "path": str(output_path),
                    "bytes": output_path.stat().st_size,
                    "sha256": sha256_file(output_path),
                    "lens": float(camera.data.lens),
                    "cameraType": camera.data.type,
                    "cameraMatrixWorld": [
                        list(row) for row in camera.matrix_world
                    ],
                    "roleState": state,
                }
            )
    finally:
        scene.camera = original["camera"]
        scene.render.engine = original["engine"]
        scene.render.filepath = original["filepath"]
        scene.render.image_settings.file_format = original["format"]
        scene.render.resolution_x = original["resolution_x"]
        scene.render.resolution_y = original["resolution_y"]
        scene.render.resolution_percentage = original["resolution_percentage"]
        if original["samples"] is not None and hasattr(scene, "cycles"):
            scene.cycles.samples = original["samples"]
            scene.cycles.seed = original["seed"]

    blend_path = Path(bpy.data.filepath).resolve() if bpy.data.filepath else None
    manifest = {
        "schemaVersion": 2,
        "generatedAt": utc_now(),
        "blenderVersion": bpy.app.version_string,
        "blendFile": str(blend_path) if blend_path else None,
        "blendSha256": sha256_file(blend_path) if blend_path and blend_path.is_file() else None,
        "scene": scene.name,
        "settings": {
            "engine": resolved_engine or original["engine"],
            "samples": (
                args.samples
                if args.samples is not None
                else original["samples"]
            ),
            "seed": args.seed,
            "resolution": [
                args.resolution_x or original["resolution_x"],
                args.resolution_y or original["resolution_y"],
            ],
            "resolutionPercentage": args.resolution_percentage,
            "viewTransform": getattr(scene.view_settings, "view_transform", None),
            "look": getattr(scene.view_settings, "look", None),
            "displayDevice": getattr(scene.display_settings, "display_device", None),
            "exposure": float(scene.view_settings.exposure),
        },
        "renders": rendered,
    }
    manifest_path = output_dir / args.manifest_name
    atomic_write_json(manifest_path, manifest)
    print(f"Manifest: {manifest_path}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ValueError, RuntimeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(2)
