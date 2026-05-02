#!/bin/bash
set -euo pipefail

echo ">>> Seeding dev data..."
python - <<'EOF'
import asyncio
import uuid
from app.database import AsyncSessionLocal
from app.models.preference import NotificationPreference

async def seed():
    async with AsyncSessionLocal() as session:
        pref = NotificationPreference(
            user_id=uuid.UUID("550e8400-e29b-41d4-a716-446655440000"),
            email_enabled=True,
            email_address="dev-user@travelhub.app",
            push_enabled=False,
            locale="es",
        )
        session.add(pref)
        await session.commit()
        print("Seed OK.")

asyncio.run(seed())
EOF
