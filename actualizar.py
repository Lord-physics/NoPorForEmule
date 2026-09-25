"""Update a ZIP installation from a pinned commit of the GitHub main branch."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
import zipfile
from pathlib import Path, PurePosixPath
from io import BytesIO

REPOSITORY = "Lord-physics/NoPorForEmule"
VERSION_FILE = ".installed_commit"
MAX_ARCHIVE_BYTES = 50 * 1024 * 1024
MAX_EXTRACTED_BYTES = 100 * 1024 * 1024
EXCLUDED = {".git", ".venv", "__pycache__", "Actualizar.bat", VERSION_FILE}


def _download(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": "NoPorForEmule-Updater"})
    with urllib.request.urlopen(request, timeout=30) as response:
        data = response.read(MAX_ARCHIVE_BYTES + 1)
    if len(data) > MAX_ARCHIVE_BYTES:
        raise ValueError("La descarga supera el tamaño permitido")
    return data


def latest_commit() -> str:
    url = f"https://api.github.com/repos/{REPOSITORY}/commits/main"
    sha = json.loads(_download(url))["sha"]
    if len(sha) != 40 or any(char not in "0123456789abcdef" for char in sha):
        raise ValueError("GitHub devolvió una revisión no válida")
    return sha


def archive_files(data: bytes, sha: str) -> dict[Path, bytes]:
    files: dict[Path, bytes] = {}
    prefix = f"NoPorForEmule-{sha}/"
    total = 0
    with zipfile.ZipFile(BytesIO(data)) as archive:
        for member in archive.infolist():
            if member.is_dir():
                continue
            if not member.filename.startswith(prefix):
                raise ValueError("El ZIP no pertenece a la revisión solicitada")
            relative = PurePosixPath(member.filename[len(prefix):])
            if (relative.is_absolute() or not relative.parts
                    or any(part in ("", ".", "..") or ":" in part for part in relative.parts)):
                raise ValueError("Ruta no válida en la actualización")
            if any(part in EXCLUDED for part in relative.parts):
                continue
            # Only regular files from the source archive may be installed.
            mode = member.external_attr >> 16
            if mode and (mode & 0o170000) not in (0, 0o100000):
                raise ValueError("El ZIP contiene un tipo de archivo no permitido")
            total += member.file_size
            if total > MAX_EXTRACTED_BYTES:
                raise ValueError("La actualización descomprimida es demasiado grande")
            destination = Path(*relative.parts)
            if destination in files or any(str(existing).casefold() == str(destination).casefold() for existing in files):
                raise ValueError("Archivo repetido en el ZIP")
            files[destination] = archive.read(member)
    if Path("main.py") not in files or Path("requirements.txt") not in files:
        raise ValueError("Faltan archivos esenciales en la actualización")
    return files


def _install_requirements(install_dir: Path, files: dict[Path, bytes], work: Path) -> None:
    if sys.prefix == sys.base_prefix:
        return  # Iniciar.bat creates and installs the virtual environment later.
    current = install_dir / "requirements.txt"
    if current.is_file() and current.read_bytes() == files[Path("requirements.txt")]:
        return
    requirements = work / "requirements.txt"
    requirements.write_bytes(files[Path("requirements.txt")])
    subprocess.run([sys.executable, "-m", "pip", "install", "-r", str(requirements)], check=True)


def install_files(install_dir: Path, files: dict[Path, bytes], sha: str) -> None:
    """Stage everything first; restore original files if replacement fails."""
    with tempfile.TemporaryDirectory(prefix=".nopor_update_", dir=install_dir) as temporary:
        work = Path(temporary)
        staged = work / "staged"
        backups = work / "backups"
        for relative, content in files.items():
            target = staged / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(content)
        _install_requirements(install_dir, files, work)
        (staged / VERSION_FILE).write_text(sha + "\n", encoding="ascii")
        moved: list[tuple[Path, Path | None]] = []
        try:
            for relative in (*files.keys(), Path(VERSION_FILE)):
                target = install_dir / relative
                # Never replace through a junction or symlink into another directory.
                inside_parents = [install_dir.joinpath(*relative.parts[:i]) for i in range(1, len(relative.parts))]
                if target.is_symlink() or any(parent.is_symlink() for parent in inside_parents):
                    raise ValueError(f"Ruta enlazada no permitida: {relative}")
                if target.exists() and not target.is_file():
                    raise ValueError(f"No se puede reemplazar una carpeta: {relative}")
                target.parent.mkdir(parents=True, exist_ok=True)
                backup = backups / relative if target.exists() else None
                if backup:
                    backup.parent.mkdir(parents=True, exist_ok=True)
                    os.replace(target, backup)
                moved.append((target, backup))
                os.replace(staged / relative, target)
        except Exception:
            for target, backup in reversed(moved):
                if target.exists():
                    target.unlink()
                if backup and backup.exists():
                    os.replace(backup, target)
            raise


def update(install_dir: Path, sha: str | None = None, archive: bytes | None = None) -> str:
    sha = sha or latest_commit()
    version = install_dir / VERSION_FILE
    if version.is_file() and version.read_text(encoding="ascii").strip() == sha:
        return "Ya tienes la última versión."
    archive = archive if archive is not None else _download(
        f"https://github.com/{REPOSITORY}/archive/{sha}.zip"
    )
    files = archive_files(archive, sha)
    install_files(install_dir, files, sha)
    return f"Actualizado a la revisión {sha[:12]}. Reinicia NoPorForEmule."


def main() -> int:
    try:
        print(update(Path(__file__).resolve().parent))
        return 0
    except (OSError, ValueError, KeyError, zipfile.BadZipFile, subprocess.CalledProcessError) as exc:
        if isinstance(exc, urllib.error.HTTPError) and exc.code in (401, 403, 404):
            print("No se puede descargar la actualización: comprueba que el repositorio sea público.", file=sys.stderr)
        else:
            print(f"No se pudo actualizar: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
