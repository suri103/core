#!/usr/bin/env python3
"""
Run the two new security migrations
"""

import os
import sys
from dotenv import load_dotenv

load_dotenv()

# Change to coredent-api directory
os.chdir('coredent-api')

print("=" * 60)
print("🚀 RUNNING NEW SECURITY MIGRATIONS")
print("=" * 60)
print()

# Fix DATABASE_URL for SQLite
database_url = os.getenv('DATABASE_URL', 'sqlite+aiosqlite:///./coredent.db')
if 'sqlite+aiosqlite' in database_url:
    database_url = database_url.replace('sqlite+aiosqlite', 'sqlite')
    os.environ['DATABASE_URL'] = database_url
    print("✅ Fixed SQLite URL for Alembic")

try:
    from alembic.config import Config
    from alembic import command
    
    # Create Alembic config
    alembic_cfg = Config("alembic.ini")
    alembic_cfg.set_main_option("sqlalchemy.url", database_url)
    
    print("🔄 Running migrations...")
    print()
    
    # Run migrations
    command.upgrade(alembic_cfg, "head")
    
    print()
    print("=" * 60)
    print("✅ MIGRATIONS COMPLETED SUCCESSFULLY!")
    print("=" * 60)
    print()
    print("New migrations applied:")
    print("  1. ✅ 20260413_1400 - Password reset token hashing")
    print("  2. ✅ 20260413_1410 - Session token hashing")
    print()
    print("Next steps:")
    print("  1. ✅ Migrations: COMPLETE")
    print("  2. ⏳ Setup Sentry: Get DSN from https://sentry.io")
    print("  3. ⏳ Test login")
    print("  4. 🚀 LAUNCH BETA!")
    
except Exception as e:
    print()
    print("=" * 60)
    print(f"❌ ERROR: {e}")
    print("=" * 60)
    sys.exit(1)
