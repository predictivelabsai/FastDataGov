"""Durable notification outbox delivery with secret references and host allowlisting."""

from __future__ import annotations

import os
import smtplib
from email.message import EmailMessage
from urllib.parse import urlparse

import httpx

from fastdatagov.config import settings
from fastdatagov.db import connect, fetch_one


def _secret(reference: str) -> str:
    if not reference.startswith("env:"):
        raise ValueError("Notification endpoints must use env: secret references")
    value=os.getenv(reference.removeprefix("env:"),"")
    if not value: raise ValueError(f"Notification secret {reference} is not configured")
    return value


def deliver(notification_id: int) -> None:
    row=fetch_one("SELECT o.*,c.channel_type,c.endpoint_ref FROM fastdatagov.notification_outbox o JOIN fastdatagov.notification_channels c ON c.id=o.channel_id WHERE o.id=%s AND o.status IN ('queued','sending') AND c.enabled",(notification_id,))
    if not row: raise ValueError("Queued notification does not exist or its channel is disabled")
    endpoint=_secret(row["endpoint_ref"]); configured=settings()
    if row["channel_type"]=="email":
        recipient=row.get("recipient") or endpoint
        if not configured.smtp_host or not recipient: raise ValueError("SMTP and a recipient are required for email delivery")
        message=EmailMessage(); message["From"]=configured.notification_from_email; message["To"]=recipient; message["Subject"]=row["subject"]; message.set_content(row["body"])
        with smtplib.SMTP(configured.smtp_host,configured.smtp_port,timeout=15) as client:
            client.starttls()
            if configured.smtp_user: client.login(configured.smtp_user,configured.smtp_password)
            client.send_message(message)
    else:
        parsed=urlparse(endpoint)
        if parsed.scheme!="https" or not parsed.hostname or parsed.hostname.lower() not in configured.webhook_hosts:
            raise ValueError("Webhook endpoint must be HTTPS and its hostname explicitly allowlisted")
        try:
            response=httpx.post(endpoint,json={"text":row["body"],"event_type":row["event_type"],"data":row["payload"]},timeout=15,follow_redirects=False)
        except httpx.HTTPError as exc:
            raise ValueError(f"Webhook transport failed: {type(exc).__name__}") from exc
        if not 200<=response.status_code<300: raise ValueError(f"Webhook returned HTTP {response.status_code}")
    with connect() as connection, connection.cursor() as cursor:
        cursor.execute("UPDATE fastdatagov.notification_outbox SET status='sent',sent_at=now(),attempts=attempts+1,last_error=NULL WHERE id=%s",(notification_id,)); connection.commit()


def fail(notification_id: int, error: Exception, terminal: bool = False) -> None:
    with connect() as connection, connection.cursor() as cursor:
        cursor.execute("UPDATE fastdatagov.notification_outbox SET status=%s,attempts=attempts+1,last_error=%s,available_at=now()+interval '1 minute' WHERE id=%s",("failed" if terminal else "queued",str(error)[:2000],notification_id)); connection.commit()
