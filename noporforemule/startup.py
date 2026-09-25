"""Optional Windows launch shortcuts; no changes until the user chooses them."""

from __future__ import annotations

import os
import subprocess
import ctypes
from pathlib import Path


SHORTCUT_NAME = "NoPorForEmule.lnk"
_CREATE = (
    "$s=New-Object -ComObject WScript.Shell; "
    "$l=$s.CreateShortcut($env:NOPOR_SHORTCUT); "
    "$l.TargetPath=$env:NOPOR_TARGET; "
    "$l.WorkingDirectory=$env:NOPOR_WORKDIR; "
    "$l.Description='Iniciar eMule y NoPorForEmule'; $l.Save()"
)
_TARGET = (
    "$s=New-Object -ComObject WScript.Shell; "
    "$l=$s.CreateShortcut($env:NOPOR_SHORTCUT); Write-Output $l.TargetPath"
)


def _run(script: str, shortcut: Path, target: Path) -> str:
    env = os.environ.copy()
    env.update(NOPOR_SHORTCUT=str(shortcut), NOPOR_TARGET=str(target), NOPOR_WORKDIR=str(target.parent))
    result = subprocess.run(
        ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", script],
        env=env, capture_output=True, text=True, check=True,
    )
    return result.stdout.strip()


def desktop_shortcut(target: Path) -> Path:
    path = ctypes.create_unicode_buffer(260)
    if ctypes.windll.shell32.SHGetFolderPathW(None, 0x10, None, 0, path) != 0:
        raise OSError("No se encuentra la carpeta Escritorio")
    desktop = Path(path.value)
    shortcut = desktop / SHORTCUT_NAME
    if shortcut.exists() and not _points_to(shortcut, target):
        raise FileExistsError(f"Ya existe otro acceso directo con ese nombre: {shortcut}")
    _run(_CREATE, shortcut, target)
    return shortcut


def startup_shortcut(target: Path) -> Path:
    return Path(os.environ["APPDATA"]) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup" / SHORTCUT_NAME


def startup_enabled(target: Path) -> bool:
    shortcut = startup_shortcut(target)
    if not shortcut.exists():
        return False
    return _points_to(shortcut, target)


def _points_to(shortcut: Path, target: Path) -> bool:
    try:
        return Path(_run(_TARGET, shortcut, target)).resolve() == target.resolve()
    except (OSError, subprocess.CalledProcessError):
        return False


def set_startup(target: Path, enabled: bool) -> None:
    shortcut = startup_shortcut(target)
    if enabled:
        if shortcut.exists() and not _points_to(shortcut, target):
            raise FileExistsError(f"Ya existe otro acceso directo con ese nombre: {shortcut}")
        shortcut.parent.mkdir(parents=True, exist_ok=True)
        _run(_CREATE, shortcut, target)
    elif startup_enabled(target):
        shortcut.unlink()
