#!/usr/bin/env python3
"""
Run Database Migrations on Railway
This script connects to Railway PostgreSQL and runs pending migrations
"""

import os
import sys
import subprocess

def run_migrations():
    """Run alembic migrations on Railway"""
    
    print("=" * 60)
    print("🚀 RUNNING DATABASE MIGRATIONS ON RAILWAY")
    print("=" * 60)
    print()
    
    # Check if railway CLI is installed
    try:
        result = subprocess.run(
            ["railway", "--version"],
            capture_output=True,
            text=True,
            check=False
        )
        if result.returncode != 0:
            print("❌ Railway CLI not installed!")
            print()
            print("Install it first:")
            print("  npm install -g @railway/cli")
            print()
            print("Or use Railway Dashboard:")
            print("  1. Go to https://railway.app")
            print("  2. Select your project")
            print("  3. Click on backend service")
            print("  4. Go to Settings → Run Command")
            print("  5. Enter: alembic upgrade head")
            print("  6. Click 'Run'")
            return False
    except FileNotFoundError:
        print("❌ Railway CLI not found!")
        print()
        print("Install it first:")
        print("  npm install -g @railway/cli")
        print()
        print("Or use Railway Dashboard:")
        print("  1. Go to https://railway.app")
        print("  2. Select your project")
        print("  3. Click on backend service")
        print("  4. Go to Settings → Run Command")
        print("  5. Enter: alembic upgrade head")
        print("  6. Click 'Run'")
        return False
    
    print("✅ Railway CLI found")
    print()
    
    # Check if logged in
    print("Checking Railway login status...")
    result = subprocess.run(
        ["railway", "whoami"],
        capture_output=True,
        text=True,
        check=False
    )
    
    if result.returncode != 0:
        print("❌ Not logged in to Railway!")
        print()
        print("Login first:")
        print("  railway login")
        return False
    
    print("✅ Logged in to Railway")
    print()
    
    # Run migrations
    print("Running migrations...")
    print("Command: railway run alembic upgrade head")
    print()
    
    try:
        # Change to coredent-api directory
        os.chdir("coredent-api")
        
        result = subprocess.run(
            ["railway", "run", "alembic", "upgrade", "head"],
            check=False
        )
        
        if result.returncode == 0:
            print()
            print("=" * 60)
            print("✅ MIGRATIONS COMPLETED SUCCESSFULLY!")
            print("=" * 60)
            print()
            print("Next steps:")
            print("1. ✅ Migrations: COMPLETE")
            print("2. ⏳ Setup Sentry: Get DSN from https://sentry.io")
            print("3. ⏳ Restart backend: railway restart")
            print("4. ⏳ Test login")
            print("5. 🚀 LAUNCH BETA!")
            return True
        else:
            print()
            print("=" * 60)
            print("❌ MIGRATION FAILED")
            print("=" * 60)
            print()
            print("Try running manually in Railway Dashboard:")
            print("1. Go to https://railway.app")
            print("2. Select your project")
            print("3. Click on backend service")
            print("4. Go to Settings → Run Command")
            print("5. Enter: alembic upgrade head")
            print("6. Click 'Run'")
            return False
            
    except Exception as e:
        print()
        print(f"❌ Error: {e}")
        print()
        print("Try running manually in Railway Dashboard:")
        print("1. Go to https://railway.app")
        print("2. Select your project")
        print("3. Click on backend service")
        print("4. Go to Settings → Run Command")
        print("5. Enter: alembic upgrade head")
        print("6. Click 'Run'")
        return False

if __name__ == "__main__":
    success = run_migrations()
    sys.exit(0 if success else 1)
