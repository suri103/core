#!/usr/bin/env python3
"""
Create Test Admin User - Simple Synchronous Version
No async dependencies needed - uses psycopg2 directly
"""

import sys
from uuid import uuid4

try:
    import psycopg2
    from psycopg2.extras import execute_values
except ImportError:
    print("❌ psycopg2 not installed")
    print("\nInstall it with:")
    print("  pip install psycopg2-binary")
    sys.exit(1)

# Get connection string from user
print("\n" + "="*60)
print("🚀 Create Test Admin User")
print("="*60)

db_url = input("\nEnter Railway PostgreSQL URL (postgresql://...): ").strip()

if not db_url:
    print("❌ No database URL provided")
    sys.exit(1)

# Parse connection string
# Format: postgresql://username:password@host:port/database
try:
    # Remove postgresql:// prefix
    if db_url.startswith("postgresql://"):
        db_url = db_url[13:]
    elif db_url.startswith("postgres://"):
        db_url = db_url[11:]
    
    # Split credentials and host
    creds, host_db = db_url.split("@")
    username, password = creds.split(":")
    
    # Split host and database
    host_port, database = host_db.split("/")
    
    if ":" in host_port:
        host, port = host_port.split(":")
        port = int(port)
    else:
        host = host_port
        port = 5432
    
    print(f"\n🔗 Connecting to database...")
    print(f"   Host: {host}:{port}")
    print(f"   Database: {database}")
    
    # Connect to database
    conn = psycopg2.connect(
        host=host,
        port=port,
        database=database,
        user=username,
        password=password
    )
    
    cursor = conn.cursor()
    
    print("\n📝 Creating practice...")
    
    # Create practice
    practice_id = str(uuid4())
    cursor.execute("""
        INSERT INTO practices (
            id, name, email, phone,
            address_street, address_city, address_state, address_zip,
            timezone, currency, created_at, updated_at
        ) VALUES (
            %s, %s, %s, %s,
            %s, %s, %s, %s,
            %s, %s, NOW(), NOW()
        )
    """, (
        practice_id,
        "Demo Dental Practice",
        "info@demodental.com",
        "555-0123",
        "123 Main Street",
        "Springfield",
        "IL",
        "62701",
        "America/Chicago",
        "USD"
    ))
    
    print("✅ Practice created")
    print("\n👤 Creating admin user...")
    
    # Password hash for "Admin123!" (bcrypt)
    password_hash = "$2b$12$R9h7cIPz0gi.URNNX3kh2OPST9/PgBBkqq8Kj7KqkL1p8T9m.Yvva"
    
    # Create admin user
    user_id = str(uuid4())
    cursor.execute("""
        INSERT INTO users (
            id, email, password_hash, first_name, last_name,
            role, practice_id, is_active, created_at, updated_at
        ) VALUES (
            %s, %s, %s, %s, %s,
            %s, %s, %s, NOW(), NOW()
        )
    """, (
        user_id,
        "admin@coredent.com",
        password_hash,
        "Admin",
        "User",
        "DENTIST",
        practice_id,
        True
    ))
    
    conn.commit()
    cursor.close()
    conn.close()
    
    print("✅ Admin user created")
    print("\n" + "="*60)
    print("✅ SUCCESS!")
    print("="*60)
    print(f"\nPractice: Demo Dental Practice")
    print(f"Practice ID: {practice_id}")
    print(f"\nAdmin Email: admin@coredent.com")
    print(f"Admin Password: Admin123!")
    print(f"Admin ID: {user_id}")
    print("\n⚠️  IMPORTANT: Change the password after first login!")
    print("="*60 + "\n")
    
except psycopg2.Error as e:
    print(f"\n❌ Database Error: {e}")
    print("\nTroubleshooting:")
    print("1. Check that the database URL is correct")
    print("2. Make sure you can connect to Railway PostgreSQL")
    print("3. Verify the tables exist (run migrations first)")
    print("4. Check that the connection string format is correct:")
    print("   postgresql://username:password@host:port/database")
    sys.exit(1)
except Exception as e:
    print(f"\n❌ Error: {e}")
    print("\nTroubleshooting:")
    print("1. Check the connection string format")
    print("2. Make sure all credentials are correct")
    print("3. Verify the database exists")
    sys.exit(1)
