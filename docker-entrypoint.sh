#!/usr/bin/env sh
set -eu

if [ "${REPOSITORY_MODE:-demo}" = "postgres" ]; then
    python -m fastdatagov.db.migrate
fi

if [ "${RUN_BACKGROUND_WORKERS:-false}" = "true" ]; then
    python -m fastdatagov.jobs.worker &
    python -m fastdatagov.jobs.scheduler &
fi

exec "$@"
