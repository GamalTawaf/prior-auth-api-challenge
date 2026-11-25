#!/bin/sh
# Bring schema to head before serving. Seed remains a separate explicit step.
set -eu
alembic upgrade head
exec "$@"
