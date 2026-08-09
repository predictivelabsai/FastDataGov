from __future__ import annotations

import logging
import time

from psycopg.types.json import Jsonb

from fastdatagov.config import settings
from fastdatagov.db import connect

log = logging.getLogger(__name__)


def schedule_due() -> dict[str, int]:
    counts = {"sync": 0, "quality": 0, "notifications": 0, "renewals": 0, "recovered": 0}
    with connect() as connection, connection.cursor() as cursor:
        cursor.execute("UPDATE fastdatagov.jobs SET status='queued',locked_by=NULL,locked_at=NULL,run_after=now(),last_error=coalesce(last_error,'')||' [worker lease expired]' WHERE status='running' AND locked_at<now()-make_interval(secs=>%s)",(settings().job_lease_seconds,))
        counts["recovered"]=cursor.rowcount
        cursor.execute("UPDATE fastdatagov.sync_runs SET status='failed',error_summary='Worker lease expired',completed_at=now() WHERE status='running' AND started_at<now()-make_interval(secs=>%s)",(settings().job_lease_seconds,))
        cursor.execute(
            """
            INSERT INTO fastdatagov.jobs (kind, payload)
            SELECT 'adapter.sync', jsonb_build_object('connection_id', c.id)
            FROM fastdatagov.connections c
            WHERE coalesce(c.last_sync_at, 'epoch'::timestamptz) < now() - make_interval(mins => %s)
              AND NOT EXISTS (SELECT 1 FROM fastdatagov.jobs j WHERE j.kind='adapter.sync'
                              AND j.status IN ('queued','running')
                              AND (j.payload->>'connection_id')::bigint=c.id)
            """,
            (settings().sync_interval_minutes,),
        )
        counts["sync"] = cursor.rowcount
        cursor.execute(
            """
            INSERT INTO fastdatagov.jobs (kind, payload)
            SELECT 'quality.run', jsonb_build_object('rule_id', qr.id)
            FROM fastdatagov.quality_rules qr
            WHERE qr.enabled=true AND qr.schedule<>'manual'
              AND coalesce(qr.next_run_at,'epoch'::timestamptz)<=now()
              AND NOT EXISTS (SELECT 1 FROM fastdatagov.jobs j WHERE j.kind='quality.run'
                              AND j.status IN ('queued','running')
                              AND (j.payload->>'rule_id')::bigint=qr.id)
            """,
            (),
        )
        counts["quality"] = cursor.rowcount
        cursor.execute("""UPDATE fastdatagov.quality_rules SET next_run_at=CASE schedule WHEN 'hourly' THEN now()+interval '1 hour' WHEN 'daily' THEN now()+interval '1 day' WHEN 'weekly' THEN now()+interval '7 days' ELSE NULL END WHERE enabled AND schedule<>'manual' AND coalesce(next_run_at,'epoch'::timestamptz)<=now()""")
        cursor.execute(
            """
            INSERT INTO fastdatagov.jobs (kind,payload)
            SELECT 'notification.send',jsonb_build_object('notification_id',o.id)
            FROM fastdatagov.notification_outbox o
            WHERE o.status='queued' AND o.available_at<=now()
              AND NOT EXISTS (SELECT 1 FROM fastdatagov.jobs j WHERE j.kind='notification.send'
                              AND j.status IN ('queued','running')
                              AND (j.payload->>'notification_id')::bigint=o.id)
            """
        )
        counts["notifications"] = cursor.rowcount
        cursor.execute(
            """INSERT INTO fastdatagov.work_items (kind,asset_id,title,description,priority,assignee_email,due_at,payload)
               SELECT 'attestation',CASE WHEN aa.scope_type='asset' THEN aa.scope_id END,
                      'Renew '||aa.responsibility||' accountability',
                      'The formal '||aa.responsibility||' attestation for '||aa.scope_type||':'||aa.scope_id||' is approaching expiry.',
                      'high',aa.assignee_email,aa.attestation_expires_at,jsonb_build_object('assignment_id',aa.id)
               FROM fastdatagov.accountability_assignments aa
               WHERE aa.attestation_expires_at BETWEEN now() AND now()+interval '30 days'
                 AND NOT EXISTS (SELECT 1 FROM fastdatagov.work_items w WHERE w.kind='attestation'
                                 AND w.status NOT IN ('resolved','rejected') AND w.payload->>'assignment_id'=aa.id::text)"""
        )
        counts["renewals"] += cursor.rowcount
        cursor.execute(
            """INSERT INTO fastdatagov.work_items (kind,asset_id,title,description,priority,assignee_email,due_at,payload)
               SELECT 'certification',c.asset_id,'Renew asset certification','The asset certification is approaching expiry.',
                      'high',a.owner_email,c.expires_at,jsonb_build_object('certification_id',c.id)
               FROM fastdatagov.certifications c JOIN fastdatagov.assets a ON a.id=c.asset_id
               WHERE c.expires_at BETWEEN now() AND now()+interval '30 days'
                 AND c.id=(SELECT max(c2.id) FROM fastdatagov.certifications c2 WHERE c2.asset_id=c.asset_id)
                 AND NOT EXISTS (SELECT 1 FROM fastdatagov.work_items w WHERE w.kind='certification'
                                 AND w.status NOT IN ('resolved','rejected') AND w.payload->>'certification_id'=c.id::text)"""
        )
        counts["renewals"] += cursor.rowcount
        cursor.execute(
            """INSERT INTO fastdatagov.work_items (kind,title,description,priority,assignee_email,due_at,payload)
               SELECT 'certification','Renew data product certification','The data product certification for '||p.name||' is approaching expiry.',
                      'high',p.owner_email,pc.expires_at,jsonb_build_object('product_certification_id',pc.id,'product_id',p.id)
               FROM fastdatagov.product_certifications pc JOIN fastdatagov.data_products p ON p.id=pc.product_id
               WHERE pc.expires_at BETWEEN now() AND now()+interval '30 days'
                 AND pc.id=(SELECT max(pc2.id) FROM fastdatagov.product_certifications pc2 WHERE pc2.product_id=pc.product_id)
                 AND NOT EXISTS (SELECT 1 FROM fastdatagov.work_items w WHERE w.kind='certification'
                                 AND w.status NOT IN ('resolved','rejected') AND w.payload->>'product_certification_id'=pc.id::text)"""
        )
        counts["renewals"] += cursor.rowcount
        connection.commit()
    return counts


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    while True:
        counts = schedule_due()
        if any(counts.values()):
            log.info("Scheduled sync=%s quality=%s notifications=%s renewals=%s recovered=%s", counts["sync"], counts["quality"], counts["notifications"], counts["renewals"],counts["recovered"])
        time.sleep(30)


if __name__ == "__main__":
    main()
