"""Launch the configured eMule executable once when using the joint launcher."""

import subprocess
from pathlib import Path

from .storage import Settings, app_data_dir


def main() -> None:
    executable = Path(Settings(app_data_dir()).load().get("emule", ""))
    if not executable.is_file() or executable.name.lower() != "emule.exe":
        raise SystemExit("Configura la ruta de eMule.exe en NoPorForEmule antes de usar el inicio conjunto.")
    subprocess.Popen([str(executable)], cwd=str(executable.parent))


if __name__ == "__main__":
    main()
