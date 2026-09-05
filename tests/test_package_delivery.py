"""Small, real ZIP fixtures for the standalone packaging helper."""
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "package_delivery.py"
spec = importlib.util.spec_from_file_location("package_delivery", SCRIPT)
package = importlib.util.module_from_spec(spec)
spec.loader.exec_module(package)


class PackageDeliveryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.out = self.root / "delivery.zip"

    def file(self, relative, content=b"fixture"):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        return path

    def test_nested_explicit_includes_are_deduplicated_and_verified(self):
        self.file("scene/final.blend", b"blend fixture")
        self.file("scene/textures/wood.png", b"texture fixture")
        self.file("notes.txt", b"notes")
        self.file("private.txt", b"not included")
        manifest = package.package_delivery(self.root, self.out, ["scene", "scene/final.blend", "notes.txt"])
        with zipfile.ZipFile(self.out) as archive:
            self.assertIsNone(archive.testzip())
            self.assertEqual(json.loads(archive.read(package.MANIFEST)), manifest)
            self.assertEqual(set(archive.namelist()), {package.MANIFEST, "scene/final.blend", "scene/textures/wood.png", "notes.txt"})
            for entry in manifest["files"]:
                content = archive.read(entry["path"])
                self.assertEqual(entry["sha256"], hashlib.sha256(content).hexdigest())
                self.assertEqual(entry["bytes"], len(content))

    def test_exclusions_and_output_archive_are_omitted(self):
        for relative in (".git/config", "cache/__pycache__/module.pyc", "scene.blend1", "render.log", "module.pyc"):
            self.file(relative)
        self.file("scene.blend")
        self.out.write_bytes(b"previous archive")
        manifest = package.package_delivery(self.root, self.out, ["."])
        self.assertEqual([entry["path"] for entry in manifest["files"]], ["scene.blend"])

    def test_rejects_invalid_paths_and_symlink_ancestors(self):
        source = self.file("scene.blend")
        (self.root / "link.blend").symlink_to(source)
        (self.root / "link-dir").symlink_to(self.root, target_is_directory=True)
        for include in ("../escape", str(source), "missing.blend", "link.blend", "link-dir/scene.blend", "C:/scene.blend", "a\\b", ""):
            with self.subTest(include=include), self.assertRaises(ValueError):
                package.package_delivery(self.root, self.out, [include])
        self.assertFalse(self.out.exists())

    def test_reserved_manifest_collision_preserves_existing_output(self):
        self.file(package.MANIFEST, b"user manifest")
        self.out.write_bytes(b"previous archive")
        with self.assertRaisesRegex(ValueError, "Reserved"):
            package.package_delivery(self.root, self.out, [package.MANIFEST])
        self.assertEqual(self.out.read_bytes(), b"previous archive")

    def test_source_mutation_fails_and_preserves_existing_output(self):
        source = self.file("scene.blend", b"original")
        self.out.write_bytes(b"previous archive")
        original_write = zipfile.ZipFile.write

        def mutate_then_write(archive, filename, *args, **kwargs):
            source.write_bytes(b"changed during packaging")
            return original_write(archive, filename, *args, **kwargs)

        with patch.object(zipfile.ZipFile, "write", mutate_then_write):
            with self.assertRaisesRegex(ValueError, "changed"):
                package.package_delivery(self.root, self.out, ["scene.blend"])
        self.assertEqual(self.out.read_bytes(), b"previous archive")
        self.assertEqual(sorted(path.name for path in self.root.iterdir()), ["delivery.zip", "scene.blend"])

    def test_requires_nonempty_explicit_selection(self):
        self.file("render.log")
        for includes in ([], ["render.log"]):
            with self.subTest(includes=includes), self.assertRaises(ValueError):
                package.package_delivery(self.root, self.out, includes)


if __name__ == "__main__":
    unittest.main()
