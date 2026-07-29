"""Create a minimal Blender audit probe scene. Run only inside Blender."""

from __future__ import annotations

import sys
from pathlib import Path

import bpy


def main() -> None:
    argv = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    if len(argv) != 1:
        raise ValueError("Expected one output .blend path after --")
    output = Path(argv[0]).expanduser().resolve()
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene

    model_collection = bpy.data.collections.new("MODEL_FINAL")
    scene.collection.children.link(model_collection)
    bpy.ops.mesh.primitive_cube_add()
    body = bpy.context.object
    for collection in list(body.users_collection):
        collection.objects.unlink(body)
    model_collection.objects.link(body)
    body.name = "AuditProbeBody"
    body["img2blender_component_id"] = "probe-body"
    body["img2blender_ignore_audit"] = True
    body["img2blender_exception_reason"] = "Integration probe: final audit must reject ignore."
    material = bpy.data.materials.new("MAT_AuditProbe")
    material.use_nodes = True
    body.data.materials.append(material)

    for name, role, location in (
        ("CAM_Reference", "reference-match", (0.0, -6.0, 1.5)),
        ("CAM_OrbitLeft", "orbit-left", (-4.0, -4.0, 2.0)),
        ("CAM_OrbitRight", "orbit-right", (4.0, -4.0, 2.0)),
        ("CAM_Critical", "critical-closeup:D01", (0.0, -3.0, 1.0)),
    ):
        camera_data = bpy.data.cameras.new(name)
        camera = bpy.data.objects.new(name, camera_data)
        scene.collection.objects.link(camera)
        camera.location = location
        camera.rotation_euler = (1.309, 0.0, 0.0)
        camera["img2blender_role"] = role
        if role == "reference-match":
            scene.camera = camera

    light_data = bpy.data.lights.new("Key", type="AREA")
    light = bpy.data.objects.new("Key", light_data)
    scene.collection.objects.link(light)
    light.location = (3.0, -3.0, 5.0)
    light_data.energy = 1000.0

    scene.render.engine = "BLENDER_EEVEE"
    scene.render.resolution_x = 2048
    scene.render.resolution_y = 2048
    scene.render.resolution_percentage = 100
    output.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(output))


if __name__ == "__main__":
    main()
