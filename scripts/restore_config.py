"""Restore an IQAlarm configuration from a backup file (JSON or ZIP)."""

import argparse
import json
import sys
import zipfile
from pathlib import Path

root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root / ".ha-test"))

from ha_live import HA  # noqa: E402


def restore_backup(backup_path: str = None):
    backups_dir = root / "backups"
    if backup_path is None:
        target = backups_dir / "latest.json"
        if not target.exists():
            target = backups_dir / "latest.zip"
    else:
        target = Path(backup_path)
        if not target.is_absolute():
            target = (root / backup_path).resolve()

    if not target.exists():
        raise FileNotFoundError(f"Backup-Datei nicht gefunden: {target}")

    print(f"Lese Backup aus: {target}")
    config_dict = None

    if target.suffix.lower() == ".zip":
        with zipfile.ZipFile(target, "r") as zf:
            if "iqalarm_config.json" not in zf.namelist():
                raise ValueError("ZIP-Archiv enthält keine 'iqalarm_config.json'")
            raw = zf.read("iqalarm_config.json").decode("utf-8")
            data = json.loads(raw)
            config_dict = data.get("config", data)
    elif target.suffix.lower() == ".json":
        data = json.loads(target.read_text(encoding="utf-8"))
        config_dict = data.get("config", data)
    else:
        raise ValueError(f"Nicht unterstütztes Dateiformat: {target.suffix}")

    if not isinstance(config_dict, dict) or "rooms" not in config_dict:
        raise ValueError("Ungültige IQAlarm-Konfiguration in der Backup-Datei")

    print("Verbinde mit Home Assistant...")
    ha = HA()
    try:
        current_res = ha.request("iqalarm/get")
        if not current_res.get("success"):
            raise RuntimeError(f"iqalarm/get fehlgeschlagen: {current_res.get('error')}")

        current_snap = current_res["result"]
        current_cfg = current_snap.get("config", {})
        live_revision = current_cfg.get("revision", 0)
        mode = current_snap.get("status", {}).get("mode")

        if current_snap.get("status", {}).get("active") or mode not in ("disarmed", "inactive"):
            raise RuntimeError(
                f"Wiederherstellung abgebrochen: Alarmanlage ist aktiv/scharf (Modus: {mode}). Bitte zuerst unscharf schalten!"
            )

        print(f"Aktuelle Revision auf Home Assistant: {live_revision}")
        # Use current live revision so HA accepts the save
        save_res = ha.request("iqalarm/config/save", config=config_dict, revision=live_revision)
        if not save_res.get("success"):
            raise RuntimeError(f"Wiederherstellung fehlgeschlagen: {save_res.get('error')}")

        restored_cfg = save_res["result"]["config"]
        print("\n" + "=" * 50)
        print("WIEDERHERSTELLUNG ERFOLGREICH!")
        print("=" * 50)
        print(f"Neue Revision:     {restored_cfg.get('revision')}")
        print(f"Räume:             {len(restored_cfg.get('rooms', {}))}")
        print(f"Sensoren:          {len(restored_cfg.get('sensors', {}))}")
        print(f"Fenster:           {len(restored_cfg.get('windows', {}))}")
        print(f"Profile:           {len(restored_cfg.get('profiles', {}))}")
        print(f"Aktionen:          {len(restored_cfg.get('actions', {}))}")
        print(f"Grundrisse:        {len(restored_cfg.get('floorplans', {}))}")
        print(f"Alarm-Stufen:      {len(restored_cfg.get('stages', {}))}")
        print("=" * 50 + "\n")
        return True
    finally:
        ha.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="IQAlarm Backup wiederherstellen")
    parser.add_argument(
        "backup_file",
        nargs="?",
        default=None,
        help="Pfad zur JSON- oder ZIP-Backup-Datei (Standard: backups/latest.json)",
    )
    args = parser.parse_args()
    restore_backup(args.backup_file)
