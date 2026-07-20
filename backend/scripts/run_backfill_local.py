#!/usr/bin/env python3
"""Run fix_broken_links.py from a dev machine that can't reach the direct DB host.

The `.env` DATABASE_URL points at Supabase's *direct* host
(db.<ref>.supabase.co), which is IPv6-only — unresolvable from IPv4-only
networks (Railway is unaffected). This wrapper rewrites only the host/user of
that DSN to the project's IPv4 session pooler (aws-1-ap-northeast-1, verified)
and runs the backfill unchanged. The password is read from .env at runtime and
never printed or stored.

    venv/bin/python scripts/run_backfill_local.py            # dry-run
    venv/bin/python scripts/run_backfill_local.py --apply    # fix live posts
    venv/bin/python scripts/run_backfill_local.py --brand quality
"""
import asyncio
import os
import re
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
POOLER_HOST = "aws-1-ap-northeast-1.pooler.supabase.com"

dsn = ""
for line in (BACKEND / ".env").read_text().splitlines():
    if line.startswith("DATABASE_URL="):
        dsn = line.split("=", 1)[1].strip()
        break

m = re.match(
    r"postgresql(?:\+asyncpg)?://([^:]+):(.+)@db\.([a-z0-9]+)\.supabase\.co:(\d+)/(\w+)",
    dsn,
)
if not m:
    sys.exit("DATABASE_URL in .env is not a Supabase direct-host DSN; run fix_broken_links.py directly.")
user, enc_password, ref, port, db = m.groups()
# Pooler routes by tenant: user becomes postgres.<project-ref>; password stays
# percent-encoded — SQLAlchemy decodes it from the DSN exactly as before.
os.environ["DATABASE_URL"] = f"postgresql://{user}.{ref}:{enc_password}@{POOLER_HOST}:{port}/{db}"

sys.path.insert(0, str(BACKEND / "scripts"))
os.chdir(BACKEND)

import fix_broken_links  # noqa: E402

sys.exit(asyncio.run(fix_broken_links.main()))
