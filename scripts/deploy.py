"""Back up and atomically install IQAlarm to a verified local or SSH /config.

No credentials are accepted or printed. SSH uses the existing agent/config with
BatchMode. Remote hosts require python3. Restart is an explicit command option.
"""

import argparse
import py_compile
import re
import shlex
import shutil
import subprocess
import tempfile
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4


def inside(path: Path, root: Path) -> Path:
    resolved, base = path.resolve(), root.resolve()
    if resolved == base or not resolved.is_relative_to(base):
        raise ValueError(f"Pfad liegt außerhalb des Zielverzeichnisses: {resolved}")
    return resolved


def install(source: Path, config: Path, restart: bool = False) -> dict:
    config = config.resolve(strict=True)
    if not ((config / "configuration.yaml").is_file() or (config / ".HA_VERSION").is_file()):
        raise ValueError("Ziel ist kein erkennbares Home-Assistant-/config-Verzeichnis")
    components = config / "custom_components"
    components.mkdir(exist_ok=True)
    inside(components, config)
    target = inside(components / "iqalarm", components)
    staging = inside(components / f".iqalarm-stage-{uuid4().hex}", components)
    backup_root = config / ".iqalarm-backups"
    backup_root.mkdir(exist_ok=True)
    backup = inside(backup_root / datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ"), config)
    previous = False
    installed = False
    try:
        shutil.copytree(source, staging, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        for path in staging.glob("*.py"):
            py_compile.compile(str(path), doraise=True)
        if target.exists():
            target.rename(backup)
            previous = True
        staging.rename(target)
        installed = True
        check = "not_available"
        if shutil.which("ha"):
            subprocess.run(["ha", "core", "check"], check=True)
            check = "passed"
            if restart:
                subprocess.run(["ha", "core", "restart"], check=True)
        elif restart:
            raise ValueError("Kein ha-CLI verfügbar; Neustart muss über die HA-Instanz erfolgen")
        return {
            "installed": str(target),
            "backup": str(backup) if previous else None,
            "ha_core_check": check,
            "restart_requested": restart,
        }
    except Exception:
        if installed and target.exists():
            failed = inside(backup_root / f"failed-{uuid4().hex}", config)
            target.rename(failed)
        if previous and backup.exists():
            backup.rename(target)
        raise
    finally:
        if staging.exists():
            inside(staging, components)
            shutil.rmtree(staging)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--ssh", help="Existing SSH host alias or user@host")
    parser.add_argument("--archive", type=Path, help="Install from an IQAlarm release archive")
    parser.add_argument("--restart", action="store_true")
    args = parser.parse_args()
    if args.ssh:
        if not re.fullmatch(r"[a-zA-Z0-9_.@:-]+", args.ssh) or args.ssh.startswith("-"):
            raise ValueError("Ungültiges SSH-Ziel")
        remote_config = str(args.config).replace("\\", "/")
        if not remote_config.startswith("/") or remote_config == "/":
            raise ValueError("Remote-/config-Pfad muss absolut sein")
        remote_dir = subprocess.run(
            ["ssh", "-o", "BatchMode=yes", args.ssh, "mktemp -d /tmp/iqalarm-deploy-XXXXXXXX"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        if not re.fullmatch(r"/tmp/iqalarm-deploy-[a-zA-Z0-9]+", remote_dir):
            raise ValueError("Remote-Temporärverzeichnis konnte nicht sicher bestimmt werden")
        with tempfile.TemporaryDirectory(prefix="iqalarm-upload-") as folder:
            from package_release import package

            archive = args.archive or package(Path(folder))
            remote_archive = remote_dir + "/iqalarm.zip"
            subprocess.run(
                ["scp", "-o", "BatchMode=yes", str(archive), f"{args.ssh}:{remote_archive}"],
                check=True,
            )
            command = (
                f"python3 - --archive {shlex.quote(remote_archive)} --config {shlex.quote(remote_config)}"
                + (" --restart" if args.restart else "")
            )
            subprocess.run(
                ["ssh", "-o", "BatchMode=yes", args.ssh, command],
                input=Path(__file__).read_bytes(),
                check=True,
            )
            subprocess.run(
                [
                    "ssh",
                    "-o",
                    "BatchMode=yes",
                    args.ssh,
                    f"rm -f {shlex.quote(remote_archive)} && rmdir {shlex.quote(remote_dir)}",
                ],
                check=True,
            )
        return
    with tempfile.TemporaryDirectory(prefix="iqalarm-install-") as folder:
        if args.archive:
            extraction = Path(folder)
            with zipfile.ZipFile(args.archive) as archive:
                for entry in archive.infolist():
                    path = inside(extraction / entry.filename, extraction)
                    if (
                        not entry.filename.startswith("custom_components/iqalarm/")
                        or path.is_symlink()
                    ):
                        raise ValueError("Ungültiger Archivinhalt")
                archive.extractall(extraction)
            source = extraction / "custom_components" / "iqalarm"
        else:
            source = Path(__file__).resolve().parents[1] / "custom_components" / "iqalarm"
        import json

        print(json.dumps(install(source, args.config, args.restart), indent=2))


if __name__ == "__main__":
    main()
