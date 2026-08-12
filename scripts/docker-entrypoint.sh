#!/bin/sh
set -e

echo "Waiting for database..."
python - <<'PY'
import os, time, sys
from urllib.parse import urlparse

url = os.environ.get("DATABASE_URL", "")
if url.startswith("sqlite"):
    sys.exit(0)

# Simple TCP wait via sqlalchemy connect
from sqlalchemy import create_engine, text

for i in range(60):
    try:
        engine = create_engine(url)
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        print("Database is ready")
        sys.exit(0)
    except Exception as e:
        print(f"DB not ready ({i+1}/60): {e}")
        time.sleep(2)
print("Database wait timed out")
sys.exit(1)
PY

echo "Running Alembic migrations..."
alembic upgrade head

ROLE="${1:-api}"
if [ "$ROLE" = "worker" ]; then
  echo "Starting video worker..."
  exec python start_worker.py
fi

echo "Starting API..."
exec uvicorn src.main:app --host 0.0.0.0 --port 8000
