"""Small actual-mesh/driver fixture for the geometry invariant adapter."""
import json
from pathlib import Path
import sys

import bpy

root = Path(sys.argv[sys.argv.index("--") + 1])
bpy.ops.object.select_all(action="SELECT")
bpy.ops.object.delete(use_global=False)
frame = bpy.data.objects.new("AssemblyFrame", None)
bpy.context.collection.objects.link(frame)
frame.location = (5, -3, 2)
frame.rotation_euler.z = 0.4


def mesh_object(name, vertices):
    mesh = bpy.data.meshes.new(name + "Mesh")
    mesh.from_pydata(vertices, [], [])
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    obj.parent = frame
    return obj


pane = mesh_object("Pane", [(x, y, z) for x in (-1, 1) for y in (-1.5, 1.5) for z in (-0.05, 0.05)])
opening = mesh_object("FrameMesh", [(x, y, 0) for x in (-2, 2) for y in (-2, 2)] +
                      [(x, y, 0) for x in (-1.2, 1.2) for y in (-1.5, 1.5)])
opening.vertex_groups.new(name="VisibleBoundary").add(list(range(4, 8)), 1.0, "REPLACE")
component = mesh_object("ArrayComponent", [(x, y, z) for x in (0, 1) for y in (0, 1) for z in (0, 1)])
array = component.modifiers.new("ActualEvaluatedArray", "ARRAY")
array.count = 2
array.relative_offset_displace = (1, 0, 0)
control = bpy.data.objects.new("RigControl", None)
bpy.context.collection.objects.link(control)
control["angle"] = 0.0
blade = bpy.data.objects.new("BladePivot", None)
bpy.context.collection.objects.link(blade)
curve = blade.driver_add("rotation_euler", 2)
variable = curve.driver.variables.new()
variable.name = "angle"
variable.type = "SINGLE_PROP"
variable.targets[0].id = control
variable.targets[0].data_path = '["angle"]'
curve.driver.expression = "angle"


def row(id, target, measurement, expected, **extra):
    return {"id": id, "featureId": "feature-1", "targets": [target], "measurement": measurement,
            "kind": "dimensions", "frame": "AssemblyFrame", "expected": expected,
            "tolerance": 0.00001, "applicablePasses": ["secondary-form"], **extra}


spec = {"referenceAnalysis": {"observedFeatures": [{"id": "feature-1"}]}, "geometryInvariants": [
    row("pane", "Pane", "pane", [2, 3, 0.1]),
    row("opening", "FrameMesh", "visible-opening", [2.4, 3, 0], vertexGroup="VisibleBoundary"),
    row("evaluated", "ArrayComponent", "component", [2, 1, 1]),
    row("rig", "BladePivot", "rig", [0, 0, 0], kind="rotation", frame="object-local", samples=[
        {"controlObject": "RigControl", "inputProperty": "angle", "inputValue": 0.5, "expected": [0, 0, 0.5]},
        {"controlObject": "RigControl", "inputProperty": "angle", "inputValue": -0.3, "expected": [0, 0, -0.3]},
    ]),
]}
(root / "spec.json").write_text(json.dumps(spec), encoding="utf-8")
bpy.ops.wm.save_as_mainfile(filepath=str(root / "fixture.blend"))
