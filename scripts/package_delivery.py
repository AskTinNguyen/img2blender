#!/usr/bin/env python3
"""Package explicit project files with a verified checksum manifest.

This verifies archive contents only; it does not reopen Blender files or validate
resource links, visual quality, or reconstruction completion.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import tempfile
import zipfile

MANIFEST = "delivery-manifest.json"


def digest_file(path):
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
            size += len(block)
    return size, digest.hexdigest()


def excluded(relative):
    return (any(part in {".git", "__pycache__"} for part in relative.parts)
            or relative.suffix.lower() in {".pyc", ".blend1", ".log"})


def collect_files(root, includes, out):
    files = {}

    def visit(path):
        relative = path.relative_to(root)
        if path.is_symlink():
            raise ValueError(f"Symlinks are not allowed: {relative}")
        if excluded(relative) or path == out:
            return
        if relative.as_posix() == MANIFEST:
            raise ValueError(f"Reserved archive filename: {MANIFEST}")
        if path.is_dir():
            for child in sorted(path.iterdir()):
                visit(child)
        elif path.is_file():
            files[relative.as_posix()] = path
        else:
            raise ValueError(f"Include is missing or not a regular file: {relative}")

    for item in includes:
        # Backslashes are rejected so the same include cannot have different
        # traversal semantics on Windows and POSIX.
        relative = PurePosixPath(item)
        if (not item or "\\" in item or relative.is_absolute()
                or ".." in relative.parts):
            raise ValueError(f"Include must stay within the project: {item!r}")
        if relative.parts and ":" in relative.parts[0]:
            raise ValueError(f"Include must be a relative project path: {item!r}")
        candidate = root.joinpath(*relative.parts)
        for ancestor in (candidate, *candidate.parents):
            if ancestor == root:
                break
            if ancestor.is_symlink():
                raise ValueError(f"Symlinks are not allowed: {item}")
        if not candidate.resolve().is_relative_to(root):
            raise ValueError(f"Include is outside the project: {item}")
        visit(candidate)
    if not files:
        raise ValueError("No deliverable files remain after exclusions")
    return dict(sorted(files.items()))


def package_delivery(project_dir, out, includes):
    original_root = Path(project_dir).expanduser().absolute()
    original_out = Path(out).expanduser().absolute()
    if original_root.is_symlink() or original_out.is_symlink():
        raise ValueError("Project root and output must not be symlinks")
    root, out = original_root.resolve(), original_out.resolve()
    if not root.is_dir():
        raise ValueError("--project-dir must be an existing directory")
    if not includes:
        raise ValueError("At least one explicit --include is required")
    if out.name == MANIFEST or out.suffix.lower() != ".zip":
        raise ValueError("--out must name a .zip archive")
    files = collect_files(root, includes, out)
    entries = []
    for relative, path in files.items():
        size, digest = digest_file(path)
        entries.append({"path": relative, "bytes": size, "sha256": digest})
    manifest = {"schemaVersion": 1, "scope": "Archive contents and checksums only", "files": entries}
    out.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix="." + out.name + ".", suffix=".tmp", dir=out.parent)
    os.close(fd)
    temporary = Path(name)
    try:
        with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for entry in entries:
                path = files[entry["path"]]
                if path.is_symlink() or path.resolve() != path:
                    raise ValueError(f"Source path changed: {entry['path']}")
                archive.write(path, entry["path"])
            archive.writestr(MANIFEST, json.dumps(manifest, indent=2) + "\n")
        with zipfile.ZipFile(temporary) as archive:
            if archive.testzip() is not None:
                raise ValueError("Archive CRC verification failed")
            archived_manifest = json.loads(archive.read(MANIFEST))
            if archived_manifest != manifest:
                raise ValueError("Archived manifest verification failed")
            for entry in archived_manifest["files"]:
                digest = hashlib.sha256()
                size = 0
                with archive.open(entry["path"]) as handle:
                    for block in iter(lambda: handle.read(1024 * 1024), b""):
                        digest.update(block)
                        size += len(block)
                if size != entry["bytes"] or digest.hexdigest() != entry["sha256"]:
                    raise ValueError(f"Archived source changed: {entry['path']}")
                path = files[entry["path"]]
                if (path.is_symlink() or path.resolve() != path
                        or digest_file(path) != (entry["bytes"], entry["sha256"])):
                    raise ValueError(f"Source changed during packaging: {entry['path']}")
        os.replace(temporary, out)
    finally:
        temporary.unlink(missing_ok=True)
    return manifest


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-dir", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--include", action="append", required=True,
                        help="Exact relative project file/directory; repeat for each inclusion")
    args = parser.parse_args(argv)
    try:
        manifest = package_delivery(args.project_dir, args.out, args.include)
    except (OSError, ValueError, zipfile.BadZipFile) as exc:
        parser.error(str(exc))
    print(f"Packaged and verified {len(manifest['files'])} files: {Path(args.out).resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
