#!/usr/bin/env python3
"""Build deterministic reference-overlay and prior-iteration comparison evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from PIL import Image, ImageChops, ImageDraw


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def open_rgb(path: Path) -> Image.Image:
    if not path.is_file():
        raise ValueError(f"Image does not exist: {path}")
    return Image.open(path).convert("RGB")


def require_same_size(images: dict[str, Image.Image]) -> tuple[int, int]:
    sizes = {image.size for image in images.values()}
    if len(sizes) != 1:
        description = ", ".join(f"{name}={image.size}" for name, image in images.items())
        raise ValueError(
            "Comparison inputs must share exact dimensions; camera/framing evidence "
            f"cannot be rescaled implicitly ({description})"
        )
    return next(iter(sizes))


def labeled_pair(left: Image.Image, right: Image.Image, left_label: str, right_label: str) -> Image.Image:
    width, height = left.size
    header = 34
    canvas = Image.new("RGB", (width * 2, height + header), (24, 24, 24))
    canvas.paste(left, (0, header))
    canvas.paste(right, (width, header))
    draw = ImageDraw.Draw(canvas)
    draw.text((10, 10), left_label, fill=(240, 240, 240))
    draw.text((width + 10, 10), right_label, fill=(240, 240, 240))
    return canvas


def record(role: str, path: Path) -> dict[str, Any]:
    return {
        "role": role,
        "kind": "comparison",
        "path": str(path.resolve()),
        "sha256": sha256_file(path),
        "bytes": path.stat().st_size,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reference", required=True)
    parser.add_argument("--current", required=True)
    parser.add_argument("--previous", required=True)
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--overlay-alpha", type=float, default=0.5)
    args = parser.parse_args()
    if not 0 < args.overlay_alpha < 1:
        parser.error("--overlay-alpha must be between 0 and 1")

    paths = {
        "reference": Path(args.reference).expanduser().resolve(),
        "current": Path(args.current).expanduser().resolve(),
        "previous": Path(args.previous).expanduser().resolve(),
    }
    images = {name: open_rgb(path) for name, path in paths.items()}
    require_same_size(images)
    output_dir = Path(args.out_dir).expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    blended = Image.blend(images["reference"], images["current"], args.overlay_alpha)
    difference = ImageChops.difference(images["reference"], images["current"])
    reference_overlay = labeled_pair(
        blended,
        difference,
        f"reference/current overlay alpha={args.overlay_alpha:.2f}",
        "absolute RGB difference",
    )
    overlay_path = output_dir / "reference-overlay.png"
    reference_overlay.save(overlay_path, optimize=False, compress_level=6)

    previous_pair = labeled_pair(
        images["previous"],
        images["current"],
        "previous iteration",
        "current iteration",
    )
    prior_path = output_dir / "previous-iteration.png"
    previous_pair.save(prior_path, optimize=False, compress_level=6)

    manifest = {
        "schemaVersion": 2,
        "inputs": {
            name: {
                "path": str(path),
                "sha256": sha256_file(path),
                "size": list(images[name].size),
            }
            for name, path in paths.items()
        },
        "evidence": [
            record("reference-overlay", overlay_path),
            record("previous-iteration", prior_path),
        ],
    }
    manifest_path = output_dir / "comparison-manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"Reference overlay: {overlay_path}")
    print(f"Previous iteration: {prior_path}")
    print(f"Manifest: {manifest_path}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ValueError as exc:
        print(f"ERROR: {exc}")
        raise SystemExit(2)
