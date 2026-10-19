"""Create a complete, standalone backup of the live IQAlarm configuration and assets."""

import datetime
import json
import shutil
import sys
import zipfile
from pathlib import Path

root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root / ".ha-test"))

from ha_live import HA, Request, urlopen  # noqa: E402


def create_backup():
    print("Verbinde mit Home Assistant...")
    ha = HA()
    try:
        response = ha.request("iqalarm/get")
        if not response.get("success"):
            raise RuntimeError(f"iqalarm/get fehlgeschlagen: {response.get('error')}")

        snapshot = response.get("result", {})
        config = snapshot.get("config", {})
        status = snapshot.get("status", {})

        now = datetime.datetime.now()
        timestamp_str = now.strftime("%Y%m%d_%H%M%S")
        iso_str = now.isoformat()

        backups_dir = root / "backups"
        backups_dir.mkdir(parents=True, exist_ok=True)

        backup_item_dir = backups_dir / f"backup_{timestamp_str}"
        backup_item_dir.mkdir(parents=True, exist_ok=True)
        floorplans_dir = backup_item_dir / "floorplans"
        floorplans_dir.mkdir(parents=True, exist_ok=True)

        downloaded_images = {}
        floorplans = config.get("floorplans", {})
        for plan_id, plan in floorplans.items():
            image_name = plan.get("image")
            if image_name:
                try:
                    url = f"{ha.origin}/api/iqalarm/floorplans/{plan_id}/image"
                    req = Request(url, headers={"Authorization": f"Bearer {ha._token}"})
                    with urlopen(req, timeout=15) as resp:
                        img_bytes = resp.read()
                    img_filename = f"{plan_id}_{image_name}"
                    img_path = floorplans_dir / img_filename
                    img_path.write_bytes(img_bytes)
                    downloaded_images[plan_id] = {
                        "name": plan.get("name"),
                        "image_filename": img_filename,
                        "original_image": image_name,
                        "bytes": len(img_bytes),
                    }
                    print(
                        f"  [+] Grundriss gesichert: {plan.get('name')} ({len(img_bytes):,} Bytes)"
                    )
                except Exception as ex:
                    print(
                        f"  [!] Warnung: Grundrissbild für '{plan.get('name')}' konnte nicht geladen werden: {ex}"
                    )

        manifest_path = root / "custom_components" / "iqalarm" / "manifest.json"
        version = "unknown"
        if manifest_path.exists():
            try:
                version = json.loads(manifest_path.read_text(encoding="utf-8")).get(
                    "version", "unknown"
                )
            except Exception:
                pass

        backup_payload = {
            "metadata": {
                "created_at": iso_str,
                "timestamp": timestamp_str,
                "version": version,
                "revision": config.get("revision"),
                "status_mode": status.get("mode"),
                "counts": {
                    "rooms": len(config.get("rooms", {})),
                    "sensors": len(config.get("sensors", {})),
                    "windows": len(config.get("windows", {})),
                    "profiles": len(config.get("profiles", {})),
                    "actions": len(config.get("actions", {})),
                    "floorplans": len(config.get("floorplans", {})),
                    "stages": len(config.get("stages", {})),
                },
                "downloaded_images": downloaded_images,
            },
            "config": config,
            "status": status,
            "windows": snapshot.get("windows", {}),
            "window_details": snapshot.get("window_details", {}),
            "information": snapshot.get("information", {}),
        }

        json_file = backup_item_dir / "iqalarm_config.json"
        json_file.write_text(
            json.dumps(backup_payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )

        # Also write standalone json in backups/ root for quick access
        flat_json_file = backups_dir / f"iqalarm_config_{timestamp_str}.json"
        flat_json_file.write_text(
            json.dumps(backup_payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )

        # Update latest.json
        latest_file = backups_dir / "latest.json"
        latest_file.write_text(
            json.dumps(backup_payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )

        # Create zip archive containing config and images
        zip_path = backups_dir / f"iqalarm_backup_{timestamp_str}.zip"
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.write(json_file, arcname="iqalarm_config.json")
            for img_path in floorplans_dir.iterdir():
                if img_path.is_file():
                    zf.write(img_path, arcname=f"floorplans/{img_path.name}")

        # Update latest.zip
        latest_zip = backups_dir / "latest.zip"
        shutil.copyfile(zip_path, latest_zip)

        print("\n" + "=" * 50)
        print("BACKUP ERFOLGREICH ERSTELLT")
        print("=" * 50)
        print(f"Zeitstempel:       {iso_str}")
        print(f"IQAlarm Version:   {version}")
        print(f"Revision:          {config.get('revision')}")
        print(f"Räume:             {len(config.get('rooms', {}))}")
        print(f"Sensoren:          {len(config.get('sensors', {}))}")
        print(f"Fenster:           {len(config.get('windows', {}))}")
        print(f"Profile:           {len(config.get('profiles', {}))}")
        print(f"Aktionen:          {len(config.get('actions', {}))}")
        print(f"Grundrisse:        {len(config.get('floorplans', {}))}")
        print(f"Alarm-Stufen:      {len(config.get('stages', {}))}")
        print("-" * 50)
        print(f"JSON-Datei:        {flat_json_file}")
        print(f"ZIP-Archiv:        {zip_path}")
        print(f"Aktuell (latest):  {latest_file} & {latest_zip}")
        print("=" * 50 + "\n")

        return {
            "success": True,
            "json_path": str(flat_json_file),
            "zip_path": str(zip_path),
            "timestamp": timestamp_str,
            "iso_time": iso_str,
            "version": version,
            "metadata": backup_payload["metadata"],
        }
    finally:
        ha.close()


if __name__ == "__main__":
    create_backup()
