"""Durable remote alarm watchdog with independently operated action workers."""

import argparse
import hashlib
import hmac
import json
import math
import re
import sqlite3
import ssl
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ID = re.compile(r"^[a-f0-9]{32}$")
SECRET = re.compile(r"^[A-Za-z0-9_-]{40,100}$")


class Monitor:
    def __init__(self, path, clock=time.time):
        self.path, self.clock = str(path), clock
        self.lock = threading.RLock()
        with self.connect() as db:
            db.executescript("""
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS systems (
                    id TEXT PRIMARY KEY, secret_hash TEXT NOT NULL,
                    enabled INTEGER NOT NULL DEFAULT 0, created REAL NOT NULL);
                CREATE TABLE IF NOT EXISTS alarms (
                    system_id TEXT NOT NULL REFERENCES systems(id), id TEXT NOT NULL,
                    deadline REAL, state TEXT NOT NULL, created REAL NOT NULL,
                    cancelled REAL, PRIMARY KEY(system_id,id));
                CREATE TABLE IF NOT EXISTS escalations (
                    system_id TEXT NOT NULL, alarm_id TEXT NOT NULL,
                    due REAL NOT NULL, recorded REAL NOT NULL,
                    action_state TEXT NOT NULL DEFAULT 'unconfigured',
                    PRIMARY KEY(system_id,alarm_id));
                CREATE INDEX IF NOT EXISTS alarms_due ON alarms(state,deadline);
            """)
            if "user_label" not in {r[1] for r in db.execute("PRAGMA table_info(systems)")}:
                db.execute(
                    "ALTER TABLE systems ADD COLUMN user_label TEXT NOT NULL DEFAULT 'deinem Freund'"
                )
            if "duration_seconds" not in {r[1] for r in db.execute("PRAGMA table_info(alarms)")}:
                db.execute("ALTER TABLE alarms ADD COLUMN duration_seconds REAL")
            if "phone_numbers" not in {r[1] for r in db.execute("PRAGMA table_info(systems)")}:
                db.execute("ALTER TABLE systems ADD COLUMN phone_numbers TEXT")

    def connect(self):
        db = sqlite3.connect(self.path, timeout=15)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        db.execute("PRAGMA synchronous=FULL")
        return db

    def expire(self):
        with self.lock, self.connect() as db:
            now = self.clock()
            db.execute(
                """INSERT OR IGNORE INTO escalations(system_id,alarm_id,due,recorded)
                SELECT system_id,id,deadline,? FROM alarms
                WHERE state='pending' AND deadline<=?""",
                (now, now),
            )
            db.execute(
                "UPDATE alarms SET state='escalated' WHERE state='pending' AND deadline<=?", (now,)
            )

    def request(self, method, path, body, credential=""):
        self.expire()
        if method == "GET" and path == "/health":
            with self.connect() as db:
                worker_installed = db.execute(
                    "SELECT 1 FROM sqlite_master WHERE type='table' AND name='sms_jobs'"
                ).fetchone()
            return 200, {
                "service": "iqalarm-monitor",
                "ok": True,
                "actions": "separate_worker" if worker_installed else "unconfigured",
            }
        with self.lock, self.connect() as db:
            if method == "POST" and path == "/v1/systems":
                key, secret = body.get("id", ""), body.get("secret", "")
                if (
                    not isinstance(key, str)
                    or not ID.fullmatch(key)
                    or not isinstance(secret, str)
                    or not SECRET.fullmatch(secret)
                ):
                    return 400, {"error": "invalid_identity"}
                # Retries after a lost registration response retain the same identity.
                old = db.execute("SELECT secret_hash FROM systems WHERE id=?", (key,)).fetchone()
                digest = hashlib.sha256(secret.encode()).hexdigest()
                if old:
                    return (
                        (200, {"id": key})
                        if hmac.compare_digest(old[0], digest)
                        else (409, {"error": "id_exists"})
                    )
                if (
                    db.execute(
                        "SELECT count(*) FROM systems WHERE created>?", (self.clock() - 3600,)
                    ).fetchone()[0]
                    >= 100
                ):
                    return 429, {"error": "enrollment_limit"}
                db.execute(
                    "INSERT INTO systems(id,secret_hash,enabled,created) VALUES(?,?,0,?)",
                    (key, digest, self.clock()),
                )
                return 201, {"id": key}
            parts = path.strip("/").split("/")
            if len(parts) < 4 or parts[:2] != ["v1", "systems"] or not ID.fullmatch(parts[2]):
                return 404, {"error": "not_found"}
            key = parts[2]
            row = db.execute("SELECT * FROM systems WHERE id=?", (key,)).fetchone()
            if not row or not hmac.compare_digest(
                row["secret_hash"], hashlib.sha256(credential.encode()).hexdigest()
            ):
                return 401, {"error": "unauthorized"}
            if len(parts) == 4 and parts[3] == "enabled" and method == "PUT":
                if type(body.get("enabled")) is not bool:
                    return 400, {"error": "invalid_enabled"}
                label = body.get("user_label", row["user_label"])
                if (
                    not isinstance(label, str)
                    or not label.strip()
                    or len(label) > 80
                    or not label.isprintable()
                ):
                    return 400, {"error": "invalid_user_label"}
                numbers_json = row["phone_numbers"]
                if "phone_numbers" in body:
                    numbers = body["phone_numbers"]
                    if not isinstance(numbers, list) or len(numbers) > 3:
                        return 400, {"error": "invalid_phone_numbers"}
                    normalized = []
                    for number in numbers:
                        if not isinstance(number, str) or len(number) > 32:
                            return 400, {"error": "invalid_phone_numbers"}
                        number = re.sub(r"[\s()/.-]", "", number)
                        if not number:
                            continue
                        if number.startswith("00"):
                            number = "+" + number[2:]
                        if not re.fullmatch(r"\+[1-9][0-9]{6,14}", number):
                            return 400, {"error": "invalid_phone_numbers"}
                        if number not in normalized:
                            normalized.append(number)
                    numbers_json = json.dumps(normalized)
                db.execute(
                    "UPDATE systems SET enabled=?,user_label=?,phone_numbers=? WHERE id=?",
                    (int(body["enabled"]), label.strip(), numbers_json, key),
                )
                return 200, {"enabled": body["enabled"]}
            if len(parts) != 5 or parts[3] != "alarms" or not ID.fullmatch(parts[4]):
                return 404, {"error": "not_found"}
            alarm = parts[4]
            old = db.execute(
                "SELECT * FROM alarms WHERE system_id=? AND id=?", (key, alarm)
            ).fetchone()
            if method == "GET":
                return (200, dict(old)) if old else (404, {"error": "not_found"})
            if method != "POST":
                return 405, {"error": "method_not_allowed"}
            if body.get("operation") == "cancel":
                state = (
                    "cancelled_after_escalation"
                    if old and old["state"] in ("escalated", "cancelled_after_escalation")
                    else "cancelled"
                )
                db.execute(
                    """INSERT INTO alarms(system_id,id,deadline,state,created,cancelled)
                    VALUES(?,?,NULL,?,?,?)
                    ON CONFLICT(system_id,id) DO UPDATE SET state=excluded.state,cancelled=excluded.cancelled""",
                    (key, alarm, state, self.clock(), self.clock()),
                )
                return 200, {"id": alarm, "state": state}
            if body.get("operation") != "start":
                return 400, {"error": "invalid_operation"}
            if old:
                return 200, {"id": alarm, "state": old["state"], "deadline": old["deadline"]}
            if not row["enabled"]:
                return 409, {"error": "monitoring_disabled"}
            remaining = body.get("remaining_seconds")
            if (
                type(remaining) not in (int, float)
                or not math.isfinite(remaining)
                or not 0 <= remaining <= 86400
            ):
                return 400, {"error": "invalid_deadline"}
            duration = body.get("duration_seconds")
            if duration is not None and (
                type(duration) not in (int, float)
                or not math.isfinite(duration)
                or not 0 < duration <= 86400
                or duration < remaining
            ):
                return 400, {"error": "invalid_duration"}
            # The client's remaining time avoids clock skew. Subsequent retries
            # cannot extend the first accepted deadline.
            deadline = self.clock() + remaining
            db.execute(
                """INSERT INTO alarms(system_id,id,deadline,state,created,cancelled,duration_seconds)
                VALUES(?,?,?,'pending',?,NULL,?)""",
                (key, alarm, deadline, self.clock(), duration),
            )
            return 201, {"id": alarm, "state": "pending", "deadline": deadline}


class Handler(BaseHTTPRequestHandler):
    server_version = "IQAlarmMonitor/1"

    def handle_request(self):
        try:
            size = int(self.headers.get("Content-Length", "0"))
            if not 0 <= size <= 4096:
                raise ValueError("size")
            body = json.loads(self.rfile.read(size)) if size else {}
            if not isinstance(body, dict):
                raise ValueError("body")
            code, result = self.server.monitor.request(
                self.command,
                self.path,
                body,
                self.headers.get("Authorization", "").removeprefix("Bearer "),
            )
        except (ValueError, json.JSONDecodeError):
            code, result = 400, {"error": "invalid_request"}
        except Exception:
            code, result = 500, {"error": "internal_error"}
        payload = json.dumps(result).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(payload)

    def setup(self):
        super().setup()
        self.connection.settimeout(10)

    def log_message(self, *_):
        pass  # No IDs, credentials or alarm details in HTTP access logs.

    do_GET = do_POST = do_PUT = handle_request


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default="/var/lib/iqalarm-monitor/monitor.sqlite3")
    parser.add_argument("--cert", required=True)
    parser.add_argument("--key", required=True)
    parser.add_argument("--port", type=int, default=9443)
    args = parser.parse_args()
    Path(args.db).parent.mkdir(parents=True, exist_ok=True)
    monitor = Monitor(args.db)
    monitor.expire()  # Catch up before accepting requests after a restart.
    server = ThreadingHTTPServer(("0.0.0.0", args.port), Handler)
    server.monitor = monitor
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    context.load_cert_chain(args.cert, args.key)
    server.socket = context.wrap_socket(server.socket, server_side=True)

    def timers():
        while True:
            try:
                monitor.expire()
            except sqlite3.Error:
                import logging

                logging.exception("Watchdog database update failed")
            time.sleep(0.5)

    threading.Thread(target=timers, daemon=True).start()
    server.serve_forever()


if __name__ == "__main__":
    main()
