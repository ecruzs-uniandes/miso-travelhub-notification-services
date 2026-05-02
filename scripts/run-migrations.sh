#!/bin/bash
set -euo pipefail

echo ">>> Running Alembic migrations..."
alembic upgrade head
echo ">>> Migrations done."
