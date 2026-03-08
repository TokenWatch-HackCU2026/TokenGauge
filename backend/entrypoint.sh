#!/bin/sh
set -e

if [ "$SEED_ON_START" = "true" ]; then
    echo "[entrypoint] Seeding database..."
    python seed.py || echo "[entrypoint] Seed failed (non-fatal), continuing..."
fi

echo "[entrypoint] Starting server..."
exec "$@"
