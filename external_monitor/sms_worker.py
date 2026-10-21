"""Durable, per-system SMS action after an external watchdog deadline."""

import argparse
import json
import logging
import math
import sqlite3
import time
from pathlib import Path

if __package__:
    from .teammessage import Outcome, TeamMessage, payload_for
else:
    from teammessage import Outcome, TeamMessage, payload_for


class SMSWorker:
    def __init__(self, database, client=None, clock=time.time):
        self.database, self.client, self.clock = str(database), client or TeamMessage(), clock
        self.invalid_systems = set()
        with self.connect() as db:
            db.execute("""CREATE TABLE IF NOT EXISTS sms_jobs (
                system_id TEXT NOT NULL, alarm_id TEXT NOT NULL,
                state TEXT NOT NULL, test_mode INTEGER NOT NULL,
                attempts INTEGER NOT NULL DEFAULT 0, next_attempt REAL NOT NULL DEFAULT 0,
                http_status INTEGER, provider_code INTEGER, updated REAL NOT NULL,
                PRIMARY KEY(system_id,alarm_id),
                FOREIGN KEY(system_id,alarm_id) REFERENCES escalations(system_id,alarm_id))""")
            # The process owns an exclusive file lock. A previous process may have
            # died after sending; never resend its in-flight requests automatically.
            db.execute("UPDATE sms_jobs SET state='uncertain' WHERE state='sending'")
            db.execute("""UPDATE escalations SET action_state='teammessage_uncertain'
                WHERE EXISTS (SELECT 1 FROM sms_jobs j WHERE j.system_id=escalations.system_id
                AND j.alarm_id=escalations.alarm_id AND j.state='uncertain')""")

    def connect(self):
        db = sqlite3.connect(self.database, timeout=15)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        db.execute("PRAGMA synchronous=FULL")
        return db

    def tick(self, config):
        active_from = config.get("active_from")
        if config.get("enabled") is not True:
            return
        if (
            type(active_from) not in (int, float)
            or not math.isfinite(active_from)
            or active_from <= 0
        ):
            raise ValueError("activation_time_required")
        systems = config.get("systems")
        if not isinstance(systems, dict):
            raise ValueError("invalid_system_mapping")
        with self.connect() as db:
            stored_phones = {
                r["id"]: r["phone_numbers"]
                for r in db.execute("SELECT id,phone_numbers FROM systems")
            }
        dispatch_configs = {}
        valid_systems = []
        for key in systems:
            dispatch_config = config
            try:
                if stored_phones.get(key) is not None:
                    recipients = json.loads(stored_phones[key])
                    if recipients == []:
                        continue  # Clearing all three UI fields explicitly removes SMS recipients.
                    dispatch_config = {
                        **config,
                        "systems": {**systems, key: {**systems[key], "recipients": recipients}},
                    }
                payload_for(dispatch_config, key, "0" * 32)
            except ValueError:
                if key not in self.invalid_systems:
                    logging.error("Invalid SMS settings for a configured installation; no SMS sent")
                self.invalid_systems.add(key)
                continue
            self.invalid_systems.discard(key)
            valid_systems.append(key)
            dispatch_configs[key] = dispatch_config
        if not valid_systems:
            return
        now = self.clock()
        with self.connect() as db:
            placeholders = ",".join("?" for _ in valid_systems)
            rows = db.execute(
                f"""SELECT e.system_id,e.alarm_id,COALESCE(j.attempts,0) AS attempts,
                s.user_label,COALESCE(a.duration_seconds,a.deadline-a.created) AS duration_seconds
                FROM escalations e JOIN alarms a ON a.system_id=e.system_id AND a.id=e.alarm_id
                JOIN systems s ON s.id=e.system_id
                LEFT JOIN sms_jobs j ON j.system_id=e.system_id AND j.alarm_id=e.alarm_id
                WHERE a.state='escalated' AND a.created>=?
                AND (j.state IS NULL OR (j.state='retry' AND j.next_attempt<=?))
                AND e.system_id IN ({placeholders})
                ORDER BY e.due LIMIT 10""",
                (active_from, now, *valid_systems),
            ).fetchall()
        for row in rows:
            key, alarm = row["system_id"], row["alarm_id"]
            if key not in config.get("systems", {}):
                continue  # An unrelated installation must never use this account's recipients.
            token, payload = payload_for(
                dispatch_configs[key], key, alarm, row["user_label"], row["duration_seconds"]
            )
            with self.connect() as db:
                db.execute("BEGIN IMMEDIATE")
                current = db.execute(
                    "SELECT state FROM alarms WHERE system_id=? AND id=?", (key, alarm)
                ).fetchone()
                job = db.execute(
                    "SELECT state,next_attempt FROM sms_jobs WHERE system_id=? AND alarm_id=?",
                    (key, alarm),
                ).fetchone()
                if current["state"] != "escalated" or (
                    job and (job["state"] != "retry" or job["next_attempt"] > self.clock())
                ):
                    continue
                db.execute(
                    """INSERT INTO sms_jobs
                    (system_id,alarm_id,state,test_mode,attempts,updated)
                    VALUES(?,?,'sending',?,1,?) ON CONFLICT(system_id,alarm_id)
                    DO UPDATE SET state='sending',test_mode=excluded.test_mode,
                    attempts=sms_jobs.attempts+1,updated=excluded.updated""",
                    (key, alarm, payload["test"], self.clock()),
                )
                db.execute(
                    """UPDATE escalations SET action_state='teammessage_sending'
                    WHERE system_id=? AND alarm_id=?""",
                    (key, alarm),
                )
            # Commit the claim before contacting the provider. Requests do not block
            # the independent watchdog process or its cancellation endpoint.
            try:
                outcome = self.client.send(token, payload)
            except Exception:
                outcome = Outcome("uncertain")
            if outcome.state == "retry" and row["attempts"] >= 2:
                outcome.state = "rejected"  # At most three documented rate-limit rejections.
            with self.connect() as db:
                db.execute(
                    """UPDATE sms_jobs SET state=?,next_attempt=?,http_status=?,
                    provider_code=?,updated=? WHERE system_id=? AND alarm_id=?""",
                    (
                        outcome.state,
                        self.clock() + outcome.retry_after,
                        outcome.http_status,
                        outcome.provider_code,
                        self.clock(),
                        key,
                        alarm,
                    ),
                )
                db.execute(
                    "UPDATE escalations SET action_state=? WHERE system_id=? AND alarm_id=?",
                    ("teammessage_" + outcome.state, key, alarm),
                )


def main():
    import fcntl

    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default="/var/lib/iqalarm-monitor/monitor.sqlite3")
    parser.add_argument("--config", default="/etc/iqalarm-monitor/teammessage.json")
    args = parser.parse_args()
    # Prevent overlapping workers and make crash recovery unambiguous.
    with open(str(Path(args.db).with_suffix(".sms.lock")), "a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        worker = SMSWorker(args.db)
        previous_error = None
        while True:
            try:
                worker.tick(json.loads(Path(args.config).read_text()))
                previous_error = None
            except (OSError, ValueError, TypeError, sqlite3.Error) as error:
                kind = type(error).__name__
                if kind != previous_error:
                    logging.error(
                        "SMS worker configuration/database error (%s); details suppressed", kind
                    )
                previous_error = kind
            time.sleep(1)


if __name__ == "__main__":
    main()
