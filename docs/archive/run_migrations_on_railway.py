#!/usr/bin/env python3
"""
Run Alembic migrations directly on Railway PostgreSQL database.
This script can be run locally to apply migrations to Railway's database.

Usage:
    python run_migrations_on_railway.py <DATABASE_URL>

Example:
    python run_migrations_on_railway.py "postgresql://user:pass@host:port/dbname"
"""

import sys
import os
from pathlib import Path

def run_migrations(database_url: str):
    """Run Alembic migrations on the specified database."""
    
    # Change to coredent-api directory
    api_dir = Path(__file__).parent / "coredent-api"
    os.chdir(api_dir)
    
    # Set the database URL environment variable
    os.environ["DATABASE_URL"] = database_url
    
    print("=" * 80)
    print("🚀 Running Alembic Migrations on Railway Database")
    print("=" * 80)
    print(f"📁 Working directory: {os.getcwd()}")
    print(f"🗄️  Database: {database_url.split('@')[1] if '@' in database_url else 'hidden'}")
    print("=" * 80)
    
    # Import alembic after changing directory
    try:
        from alembic.config import Config
        from alembic import command
    except ImportError:
        print("❌ Error: alembic not installed")
        print("Run: pip install alembic")
        sys.exit(1)
    
    # Create Alembic config
    alembic_cfg = Config("alembic.ini")
    alembic_cfg.set_main_option("sqlalchemy.url", database_url)
    
    try:
        # Show current revision
        print("\n📊 Checking current database revision...")
        command.current(alembic_cfg, verbose=True)
        
        # Run migrations
        print("\n⬆️  Upgrading to head...")
        command.upgrade(alembic_cfg, "head")
        
        # Show final revision
        print("\n✅ Migration complete! Current revision:")
        command.current(alembic_cfg, verbose=True)
        
        # Show migration history
        print("\n📜 Migration history:")
        command.history(alembic_cfg, verbose=True)
        
        print("\n" + "=" * 80)
        print("✅ ALL MIGRATIONS APPLIED SUCCESSFULLY!")
        print("=" * 80)
        print("\n📋 Applied migrations:")
        print("  1. 20260318_1311 - Initial migration (all tables)")
        print("  2. 20260407_1130 - GST fields for invoices")
        print("  3. 20260407_1200 - Performance indexes")
        print("  4. 20260407_1730 - Subscription tables")
        print("  5. 20260408_1800 - Account lockout fields")
        print("  6. 20260408_1830 - Email verification fields")
        print("\n🎉 Your Railway database is now up to date!")
        
    except Exception as e:
        print(f"\n❌ Error running migrations: {e}")
        print("\nTroubleshooting:")
        print("1. Verify DATABASE_URL is correct")
        print("2. Check network connectivity to Railway")
        print("3. Ensure database exists and is accessible")
        sys.exit(1)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python run_migrations_on_railway.py <DATABASE_URL>")
        print("\nExample:")
        print('  python run_migrations_on_railway.py "postgresql://user:pass@host:port/dbname"')
        print("\nTo get your Railway DATABASE_URL:")
        print("1. Go to Railway dashboard")
        print("2. Select your PostgreSQL service")
        print("3. Go to Variables tab")
        print("4. Copy the DATABASE_URL value")
        sys.exit(1)
    
    database_url = sys.argv[1]
    
    if not database_url.startswith("postgresql://"):
        print("❌ Error: DATABASE_URL must start with 'postgresql://'")
        sys.exit(1)
    
    run_migrations(database_url)
