#!/usr/bin/env python3
"""
Check what tables exist in Railway PostgreSQL database.
Usage: python check_railway_database.py <DATABASE_URL>
"""

import sys
import psycopg2
from psycopg2 import sql

def check_database(database_url: str):
    """Check what tables and migration status exist in the database."""
    
    print("=" * 80)
    print("🔍 Checking Railway PostgreSQL Database")
    print("=" * 80)
    
    try:
        # Connect to database
        conn = psycopg2.connect(database_url)
        cur = conn.cursor()
        
        # Check if alembic_version table exists
        cur.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_name = 'alembic_version'
            );
        """)
        has_alembic = cur.fetchone()[0]
        
        if has_alembic:
            print("\n✅ Alembic version table exists")
            cur.execute("SELECT version_num FROM alembic_version;")
            version = cur.fetchone()
            if version:
                print(f"📍 Current migration version: {version[0]}")
            else:
                print("⚠️  No migration version recorded (migrations not run yet)")
        else:
            print("\n❌ Alembic version table does NOT exist")
            print("   This means NO migrations have been run yet")
        
        # List all tables
        print("\n📋 Tables in database:")
        cur.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public'
            ORDER BY table_name;
        """)
        tables = cur.fetchall()
        
        if tables:
            print(f"\n   Found {len(tables)} tables:")
            for table in tables:
                print(f"   - {table[0]}")
        else:
            print("\n   ❌ NO TABLES FOUND - Database is empty!")
            print("   Migrations need to run to create tables")
        
        # Check for enum types
        print("\n🔤 Enum types in database:")
        cur.execute("""
            SELECT typname 
            FROM pg_type 
            WHERE typtype = 'e'
            ORDER BY typname;
        """)
        enums = cur.fetchall()
        
        if enums:
            print(f"\n   Found {len(enums)} enum types:")
            for enum in enums:
                print(f"   - {enum[0]}")
        else:
            print("\n   No enum types found")
        
        cur.close()
        conn.close()
        
        print("\n" + "=" * 80)
        if not tables or len(tables) <= 1:  # Only alembic_version or nothing
            print("❌ DATABASE IS EMPTY - Migrations have not completed")
            print("=" * 80)
            print("\n💡 Next Steps:")
            print("1. Wait for Railway backend deployment to complete")
            print("2. Migrations will run automatically on startup")
            print("3. Check deployment logs for migration progress")
        else:
            print("✅ DATABASE HAS TABLES - Some migrations have run")
            print("=" * 80)
            print("\n💡 If migrations are incomplete:")
            print("1. Check Railway deployment logs for errors")
            print("2. Fix any migration errors")
            print("3. Redeploy to continue migrations")
        
    except Exception as e:
        print(f"\n❌ Error connecting to database: {e}")
        print("\nTroubleshooting:")
        print("1. Verify DATABASE_URL is correct")
        print("2. Check network connectivity to Railway")
        print("3. Ensure database service is running")
        sys.exit(1)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python check_railway_database.py <DATABASE_URL>")
        print("\nExample:")
        print('  python check_railway_database.py "postgresql://user:pass@host:port/dbname"')
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
    
    check_database(database_url)
