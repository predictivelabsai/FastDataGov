"""Apply append-only SQL migrations with an advisory lock."""

from __future__ import annotations

from pathlib import Path

import psycopg

from fastdatagov.config import settings

MIGRATIONS = Path(__file__).with_name("migrations")
LOCK_ID = 624_108_337


def migrate() -> list[str]:
    applied_now: list[str] = []
    with psycopg.connect(settings().database_url) as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT pg_advisory_lock(%s)", (LOCK_ID,))
            try:
                cursor.execute("CREATE SCHEMA IF NOT EXISTS fast_datagov")
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS fast_datagov.schema_migrations (
                        version TEXT PRIMARY KEY,
                        applied_at TIMESTAMPTZ NOT NULL DEFAULT now()
                    )
                    """
                )
                connection.commit()
                cursor.execute("SELECT version FROM fast_datagov.schema_migrations")
                applied = {row[0] for row in cursor.fetchall()}

                for path in sorted(MIGRATIONS.glob("*.sql")):
                    if path.name in applied:
                        continue
                    cursor.execute(path.read_text())
                    cursor.execute(
                        "INSERT INTO fast_datagov.schema_migrations (version) VALUES (%s)",
                        (path.name,),
                    )
                    connection.commit()
                    applied_now.append(path.name)
            finally:
                cursor.execute("SELECT pg_advisory_unlock(%s)", (LOCK_ID,))
                connection.commit()
    return applied_now


def main() -> None:
    versions = migrate()
    if versions:
        print("Applied migrations: " + ", ".join(versions))
    else:
        print("Database is current")


if __name__ == "__main__":
    main()
