#!/usr/bin/env python3
"""Probe an exact Blender binary in isolated processes before expensive renders.

Host usage: python3 render_preflight.py --blender /path/to/blender \
    --scene checkpoint.blend --out render-preflight.json --device auto

The supplied file is opened read-only in each process. A disposable 32px Cycles
scene tests runtime/backend health, not source-scene renderability or fidelity.
Each attempt has its own timeout; GPU failure (including crash or timeout) gets
one fresh CPU attempt. Neither scenes nor user preferences are saved.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time

BACKENDS = ("OPTIX", "CUDA", "METAL", "HIP", "ONEAPI")
CYCLES_ENV = ("CYCLES_METAL_SPECIALIZATION_LEVEL", "CYCLES_METAL_ADAPTIVE_COMPILE")


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent,
                                     prefix="." + path.name, delete=False) as handle:
        temporary = Path(handle.name)
        try:
            json.dump(value, handle, indent=2)
            handle.write("\n")
        except BaseException:
            temporary.unlink(missing_ok=True)
            raise
    try:
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def run_attempt(blender, scene, directory, device, timeout, environment, metalrt):
    """Keep crash/timeout evidence even when Blender cannot finish its JSON report."""
    report_path = directory / (device.lower() + ".json")
    command = [str(blender), "--factory-startup", "--disable-autoexec", "--background",
               str(scene), "--python-exit-code", "2", "--python", str(Path(__file__).resolve()),
               "--", "--probe", "--report", str(report_path), "--device", device,
               "--metalrt", metalrt]
    attempt = {"requestedDevice": device, "exitCode": None, "timedOut": False,
               "success": False, "error": None, "probe": None}
    started = time.monotonic()
    # Log tails stay in this temporary directory. Do not persist arbitrary Blender
    # stdout (add-ons/files may print private data); manifest records our own errors.
    with (directory / (device.lower() + ".log")).open("wb") as log:
        try:
            result = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT,
                                    timeout=timeout, env=environment, check=False)
            attempt["exitCode"] = result.returncode
        except subprocess.TimeoutExpired:
            attempt["timedOut"] = True
            attempt["error"] = f"Blender exceeded the {timeout:g}s per-attempt timeout"
        except OSError as exc:
            attempt["error"] = f"Could not start Blender: {exc}"
    attempt["durationSeconds"] = round(time.monotonic() - started, 3)
    try:
        report = json.loads(report_path.read_text(encoding="utf-8"))
        if not isinstance(report, dict) or not isinstance(report.get("success"), bool):
            raise ValueError("missing boolean success")
        if report["success"] and (
            report.get("effectiveDevice") not in ("CPU", *BACKENDS)
            or not isinstance(report.get("blender"), dict)
            or not isinstance(report.get("renderSettings"), dict)
            or not report.get("renderBytes", 0) > 0
        ):
            raise ValueError("incomplete successful probe report")
        attempt["probe"] = report
    except (OSError, ValueError, TypeError) as exc:
        if attempt["error"] is None:
            attempt["error"] = f"Missing or malformed probe report: {exc}"
    if attempt["error"] is None:
        if attempt["exitCode"] != 0:
            attempt["error"] = f"Blender exited with code {attempt['exitCode']}"
        elif not attempt["probe"]["success"]:
            attempt["error"] = attempt["probe"].get("error") or "Probe did not complete"
        else:
            attempt["success"] = True
    return attempt


def preflight(blender, scene, out, device="auto", timeout=60, cycles_env=None, metalrt="auto"):
    blender, scene, out = (Path(value).expanduser().resolve() for value in (blender, scene, out))
    if not blender.is_file() or not os.access(blender, os.X_OK):
        raise ValueError("--blender must name the exact executable file")
    if not scene.is_file() or scene.suffix.lower() != ".blend":
        raise ValueError("--scene must name an existing .blend file")
    if out in (scene, blender):
        raise ValueError("--out must not overwrite the scene or Blender executable")
    if not math.isfinite(timeout) or timeout <= 0:
        raise ValueError("--timeout must be finite and positive")
    if device not in ("auto", "CPU", *BACKENDS):
        raise ValueError("Unsupported device")
    if metalrt not in ("auto", "on", "off"):
        raise ValueError("Unsupported MetalRT setting")
    overrides = dict(cycles_env or {})
    if any(key not in CYCLES_ENV for key in overrides):
        raise ValueError("Only documented Cycles environment names are allowed: " + ", ".join(CYCLES_ENV))
    environment = os.environ.copy()
    environment.update(overrides)
    manifest = {
        "schemaVersion": 1, "generatedAt": dt.datetime.now(dt.timezone.utc).isoformat(),
        "blenderExecutable": str(blender), "blendFile": str(scene), "blendSha256": sha256(scene),
        "scope": "Temporary 32x32 one-sample Cycles scene; source scene opened but not rendered",
        "requestedDevice": device, "requestedMetalRT": metalrt, "timeoutPerAttemptSeconds": timeout,
        "cyclesEnvironment": {key: environment[key] for key in CYCLES_ENV if key in environment},
        "cyclesEnvironmentOverrides": overrides,
        "attempts": [], "success": False, "effectiveDevice": None, "cpuFallback": False,
    }
    with tempfile.TemporaryDirectory(prefix="img2blender-preflight-") as temp:
        directory = Path(temp)
        for candidate in (["CPU"] if device == "CPU" else [device, "CPU"]):
            if manifest["attempts"]:
                manifest["cpuFallback"] = True
            attempt = run_attempt(blender, scene, directory, candidate, timeout, environment, metalrt)
            manifest["attempts"].append(attempt)
            write_json(out, manifest)
            if attempt["success"]:
                manifest["success"] = True
                manifest["effectiveDevice"] = attempt["probe"]["effectiveDevice"]
                # Auto can select CPU directly if no GPU is exposed by this build.
                if device != "CPU" and manifest["effectiveDevice"] == "CPU":
                    manifest["cpuFallback"] = True
                break
    manifest["blendUnchanged"] = sha256(scene) == manifest["blendSha256"]
    if not manifest["blendUnchanged"]:
        manifest["success"] = False
        manifest["error"] = "Source .blend changed during preflight"
    write_json(out, manifest)
    return manifest


def probe_main(argv):
    """Blender-only entry point; all state changes die with this subprocess."""
    import bpy
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", required=True)
    parser.add_argument("--device", required=True)
    parser.add_argument("--metalrt", default="auto")
    args = parser.parse_args(argv)
    report = {"success": False, "effectiveDevice": None, "phase": "initialize"}

    def checkpoint():
        write_json(args.report, report)

    def text_value(value):
        return value.decode("utf-8", "replace") if isinstance(value, bytes) else str(value)

    def settings(scene):
        return {"engine": scene.render.engine,
                "device": getattr(getattr(scene, "cycles", None), "device", None),
                "samples": getattr(getattr(scene, "cycles", None), "samples", None),
                "resolution": [scene.render.resolution_x, scene.render.resolution_y],
                "resolutionPercentage": scene.render.resolution_percentage,
                "useDenoising": getattr(getattr(scene, "cycles", None), "use_denoising", None)}

    try:
        report["blender"] = {key: text_value(getattr(bpy.app, key, "")) for key in
                             ("version_string", "build_hash", "build_branch", "build_date", "build_time", "build_platform")}
        report["sourceRenderSettings"] = settings(bpy.context.scene)
        report["phase"] = "device-discovery"
        checkpoint()
        addon = bpy.context.preferences.addons.get("cycles")
        if addon is None:
            bpy.ops.preferences.addon_enable(module="cycles")
            addon = bpy.context.preferences.addons.get("cycles")
        if addon is None:
            raise RuntimeError("This Blender build has no Cycles add-on")
        prefs = addon.preferences
        try:
            types = prefs.get_device_types(bpy.context)
            supported = [item[0] for item in types if item[0] in BACKENDS]
        except (AttributeError, TypeError):
            prop = prefs.bl_rna.properties.get("compute_device_type")
            supported = [item.identifier for item in prop.enum_items if item.identifier in BACKENDS] if prop else []
        report["supportedBackends"] = supported
        report["devices"] = []
        report["discoveryErrors"] = []
        requested = args.device
        candidates = [backend for backend in BACKENDS if backend in supported] if requested == "auto" else [requested]
        selected = "CPU"
        for backend in candidates:
            if backend == "CPU":
                break
            if backend not in supported:
                raise RuntimeError(f"Requested backend {backend} is unavailable in this Blender build")
            report["probingBackend"] = backend
            checkpoint()
            try:
                prefs.compute_device_type = backend
                if hasattr(prefs, "get_devices_for_type"):
                    # Query only this backend: refresh_devices probes every GPU
                    # driver, including unrelated drivers that may crash.
                    prefs.get_devices_for_type(backend)
                elif hasattr(prefs, "refresh_devices"):
                    prefs.refresh_devices()
                else:
                    prefs.get_devices()
                devices = list(prefs.devices)
                report["devices"].extend({"name": d.name, "type": d.type, "id": d.id} for d in devices)
                if any(d.type == backend for d in devices):
                    selected = backend
                    for item in devices:
                        item.use = item.type == backend
                    break
            except Exception as exc:
                report["discoveryErrors"].append({"backend": backend, "error": str(exc)})
                if requested != "auto":
                    raise
        if requested not in ("auto", "CPU") and selected == "CPU":
            raise RuntimeError(f"No usable {requested} device was found")
        report["effectiveDevice"] = selected
        report["selectedDevices"] = [{"name": d.name, "type": d.type, "id": d.id}
                                     for d in prefs.devices if d.use and d.type == selected]
        if selected == "CPU":
            # Never enumerate GPU drivers on the independent CPU fallback.
            if hasattr(prefs, "get_devices_for_type"):
                prefs.get_devices_for_type("CPU")
            for item in prefs.devices:
                item.use = item.type == "CPU"
            report["selectedDevices"] = [{"name": d.name, "type": d.type, "id": d.id}
                                         for d in prefs.devices if d.type == "CPU"]
        report["metalRT"] = {"requested": args.metalrt, "property": None, "effective": None}
        if selected == "METAL":
            for name in ("metalrt", "use_metalrt"):
                prop = prefs.bl_rna.properties.get(name)
                if prop is None:
                    continue
                if args.metalrt != "auto":
                    value = args.metalrt == "on" if prop.type == "BOOLEAN" else args.metalrt.upper()
                    if prop.type == "ENUM" and value not in {item.identifier for item in prop.enum_items}:
                        raise RuntimeError(f"MetalRT value {value} unsupported by {name}")
                    setattr(prefs, name, value)
                report["metalRT"].update(property=name, effective=getattr(prefs, name))
                break
            else:
                if args.metalrt != "auto":
                    raise RuntimeError("This Cycles build exposes no configurable MetalRT property")
        report["phase"] = "scene-setup"
        checkpoint()
        scene = bpy.data.scenes.new("img2blender_runtime_probe")
        scene.render.engine = "CYCLES"
        scene.cycles.device = "CPU" if selected == "CPU" else "GPU"
        scene.cycles.samples = 1
        scene.cycles.use_denoising = False
        scene.render.resolution_x = scene.render.resolution_y = 32
        scene.render.resolution_percentage = 100
        scene.render.image_settings.file_format = "PNG"
        scene.render.filepath = str(Path(args.report).with_suffix(".png"))
        camera = bpy.data.objects.new("probe_camera", bpy.data.cameras.new("probe_camera"))
        scene.collection.objects.link(camera)
        camera.location = (0, 0, 3)
        scene.camera = camera
        mesh = bpy.data.meshes.new("probe_triangle")
        mesh.from_pydata([(-1, -1, 0), (1, -1, 0), (0, 1, 0)], [], [(0, 1, 2)])
        scene.collection.objects.link(bpy.data.objects.new("probe_triangle", mesh))
        world = bpy.data.worlds.new("probe_world")
        world.use_nodes = True
        world.node_tree.nodes.get("Background").inputs["Color"].default_value = (0.5, 0.5, 0.5, 1)
        scene.world = world
        report["renderSettings"] = settings(scene)
        report["phase"] = "render"
        checkpoint()
        bpy.ops.render.render(write_still=True, scene=scene.name)
        image = Path(scene.render.filepath)
        if not image.is_file() or image.stat().st_size == 0:
            raise RuntimeError("Tiny probe render produced no image")
        report["renderBytes"] = image.stat().st_size
        report["success"] = True
        report["phase"] = "complete"
    except Exception as exc:
        report["error"] = f"{type(exc).__name__}: {exc}"
    checkpoint()
    return 0 if report["success"] else 2


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--blender", required=True, help="Exact executable path; no PATH lookup")
    parser.add_argument("--scene", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--device", choices=("auto", "CPU", *BACKENDS), default="auto")
    parser.add_argument("--timeout", type=float, default=60, help="Seconds per attempt (at most two attempts)")
    parser.add_argument("--metalrt", choices=("auto", "on", "off"), default="auto",
                        help="auto preserves the factory preference; on/off require a supported runtime property")
    parser.add_argument("--cycles-env", action="append", default=[], metavar="NAME=VALUE",
                        help="Explicit subprocess-only override: " + ", ".join(CYCLES_ENV))
    args = parser.parse_args(argv)
    overrides = {}
    for value in args.cycles_env:
        key, sep, content = value.partition("=")
        if not sep or key not in CYCLES_ENV:
            parser.error("--cycles-env requires an allowlisted NAME=VALUE")
        overrides[key] = content
    try:
        manifest = preflight(args.blender, args.scene, args.out, args.device, args.timeout, overrides, args.metalrt)
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    print(f"Preflight {'passed' if manifest['success'] else 'failed'}: {Path(args.out).expanduser().resolve()}")
    return 0 if manifest["success"] else 2


if __name__ == "__main__":
    if "--" in sys.argv and sys.argv[sys.argv.index("--") + 1:][:1] == ["--probe"]:
        raise SystemExit(probe_main(sys.argv[sys.argv.index("--") + 2:]))
    raise SystemExit(main())
