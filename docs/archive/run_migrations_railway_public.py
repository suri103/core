#!/usr/bin/env python3
"""
Run Alembic migrations on Railway PostgreSQL
Uses the public database URL
"""

import subprocess
import sys
import os

print("\n" + "="*70)
print("🚀 Run Migrations on Railway PostgreSQL")
print("="*70)

db_url = input("\nEnter Railway PostgreSQL public URL (postgresql://...): ").strip()

if not db_url:
    print("❌ No URL provided")
    sys.exit(1)

if not db_url.startswith("postgresql://"):
    print("❌ Invalid URL format")
    sys.exit(1)

print("\n📝 Setting DATABASE_URL environment variable...")
os.environ["DATABASE_URL"] = db_url

print("🔄 Running migrations...")
print("   This may take a minute...\n")

try:
    # Change to coredent-api directory
    os.chdir("coredent-api")
    
    # Run alembic upgrade
    result = subprocess.run(
        ["alembic", "upgrade", "head"],
        capture_output=True,
        text=True
    )
    
    if result.returncode == 0:
        print("✅ Migrations completed successfully!")
        print("\n" + result.stdout)
        print("\n" + "="*70)
        print("✅ All tables created!")
        print("="*70)
        print("\nNow you can run:")
        print("  python create_test_user_simple.py")
        print("\nAnd create the test admin user.")
        print("="*70 + "\n")
    else:
        print("❌ Migration failed!")
        print("\nError output:")
        print(result.stderr)
        sys.exit(1)
        
except Exception as e:
    print(f"❌ Error: {e}")
    sys.exit(1)
