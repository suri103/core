#!/usr/bin/env python3
"""
Run migrations against Railway database
Usage: python run_migrations_railway.py
"""

import os
import subprocess
import sys

print("=" * 60)
print("Railway Database Migrations")
print("=" * 60)
print()

# Check if DATABASE_URL is set
database_url = os.getenv("DATABASE_URL")

if not database_url:
    print("ERROR: DATABASE_URL environment variable is not set!")
    print()
    print("Please set it first:")
    print('  $env:DATABASE_URL="postgresql://..."')
    print()
    print("Get the DATABASE_URL from:")
    print("  Railway Dashboard → PostgreSQL service → Variables tab")
    print()
    sys.exit(1)

print(f"✓ DATABASE_URL is set")
print(f"  Database: {database_url.split('@')[1] if '@' in database_url else 'unknown'}")
print()

# Change to coredent-api directory
api_dir = os.path.join(os.path.dirname(__file__), "coredent-api")
if os.path.exists(api_dir):
    os.chdir(api_dir)
    print(f"✓ Changed to: {api_dir}")
else:
    print(f"ERROR: Directory not found: {api_dir}")
    sys.exit(1)

print()
print("Running migrations...")
print("-" * 60)

# Run alembic upgrade
try:
    result = subprocess.run(
        ["alembic", "upgrade", "head"],
        check=True,
        capture_output=False
    )
    print("-" * 60)
    print()
    print("✓ Migrations completed successfully!")
    print()
    print("=" * 60)
    
except subprocess.CalledProcessError as e:
    print("-" * 60)
    print()
    print(f"✗ Migration failed with error code: {e.returncode}")
    print()
    print("=" * 60)
    sys.exit(1)
    
except FileNotFoundError:
    print("-" * 60)
    print()
    print("✗ ERROR: 'alembic' command not found!")
    print()
    print("Make sure you have alembic installed:")
    print("  pip install alembic")
    print()
    print("=" * 60)
    sys.exit(1)
