from __future__ import annotations

import logging
import os
import socket
import time

import psycopg

from fastdatagov.config import settings
from fastdatagov.db import connect
from fastdatagov.jobs.runtime import check_connection_health, run_quality, sync_connection, write_tags
from fastdatagov.notifications import deliver as deliver_notification, fail as fail_notification

log = logging.getLogger(__name__)
WORKER_ID = f"{socket.gethostname()}:{os.getpid()}"


def claim_job() -> dict | None:
    with connect() as connection, connection.cursor(row_factory=psycopg.rows.dict_row) as cursor:
        cursor.execute(
            """
            WITH candidate AS (
                SELECT id FROM fastdatagov.jobs
                WHERE status='queued' AND run_after <= now() AND attempts < max_attempts
                ORDER BY run_after, id
                FOR UPDATE SKIP LOCKED LIMIT 1
            )
            UPDATE fastdatagov.jobs j SET status='running', locked_by=%s, locked_at=now(), attempts=attempts+1
            FROM candidate WHERE j.id=candidate.id RETURNING j.*
            """,
            (WORKER_ID,),
        )
        job = cursor.fetchone()
        connection.commit()
        return job


def finish_job(job_id: int) -> None:
    with connect() as connection, connection.cursor() as cursor:
        cursor.execute("UPDATE fastdatagov.jobs SET status='succeeded', completed_at=now() WHERE id=%s", (job_id,))
        connection.commit()


def fail_job(job: dict, error: Exception) -> None:
    terminal = job["attempts"] >= job["max_attempts"]
    with connect() as connection, connection.cursor() as cursor:
        cursor.execute(
            "UPDATE fastdatagov.jobs SET status=%s, last_error=%s, run_after=now() + make_interval(secs => %s), locked_by=NULL, locked_at=NULL WHERE id=%s",
            ("failed" if terminal else "queued", str(error)[:2000], min(300, 2 ** job["attempts"]), job["id"]),
        )
        connection.commit()


def process(job: dict) -> None:
    if job["kind"] == "adapter.sync":
        sync_connection(int(job["payload"]["connection_id"]))
    elif job["kind"] == "quality.run":
        run_quality(int(job["payload"]["rule_id"]))
    elif job["kind"] == "adapter.health":
        check_connection_health(int(job["payload"]["connection_id"]))
    elif job["kind"] == "notification.send":
        deliver_notification(int(job["payload"]["notification_id"]))
    elif job["kind"] == "adapter.tags":
        write_tags(int(job["payload"]["connection_id"]),str(job["payload"]["asset_external_id"]),dict(job["payload"]["tags"]))
    else:
        raise ValueError(f"Unknown job kind: {job['kind']}")


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    log.info("Worker %s started", WORKER_ID)
    while True:
        job = claim_job()
        if not job:
            time.sleep(settings().job_poll_seconds)
            continue
        try:
            process(job)
            finish_job(job["id"])
        except Exception as exc:  # noqa: BLE001
            log.exception("Job %s failed", job["id"])
            if job["kind"]=="notification.send":
                fail_notification(int(job["payload"]["notification_id"]),exc,job["attempts"]>=job["max_attempts"])
            fail_job(job, exc)


if __name__ == "__main__":
    main()
