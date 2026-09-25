import tempfile
import unittest
import zipfile
from io import BytesIO
from pathlib import Path

from actualizar import archive_files, update


SHA = "a" * 40


def make_archive(files):
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for name, data in files.items():
            archive.writestr(f"NoPorForEmule-{SHA}/{name}", data)
    return buffer.getvalue()


class UpdateTests(unittest.TestCase):
    def test_updates_program_and_preserves_local_data(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "requirements.txt").write_bytes(b"nudenet==3.4.0\n")
            (root / "main.py").write_bytes(b"old")
            (root / ".venv").mkdir()
            (root / ".venv" / "personal.txt").write_bytes(b"keep")
            (root / "personal.txt").write_bytes(b"keep")
            archive = make_archive({
                "main.py": b"new",
                "requirements.txt": b"nudenet==3.4.0\n",
                "noporforemule/app.py": b"code",
                ".venv/personal.txt": b"overwrite",
            })
            self.assertIn("Actualizado", update(root, SHA, archive))
            self.assertEqual((root / "main.py").read_bytes(), b"new")
            self.assertEqual((root / ".venv" / "personal.txt").read_bytes(), b"keep")
            self.assertEqual((root / "personal.txt").read_bytes(), b"keep")
            self.assertEqual((root / ".installed_commit").read_text().strip(), SHA)
            self.assertIn("última versión", update(root, SHA, b"invalid zip"))

    def test_rejects_path_traversal(self):
        archive = make_archive({
            "main.py": b"new", "requirements.txt": b"", "../outside.py": b"bad",
        })
        with self.assertRaises(ValueError):
            archive_files(archive, SHA)


if __name__ == "__main__":
    unittest.main()
