#!/usr/bin/env python3
"""
Fix Admin Password - Update password hash in database
"""

import sys

try:
    import psycopg2
except ImportError:
    print("❌ psycopg2 not installed")
    print("\nInstall it with:")
    print("  pip install psycopg2-binary")
    sys.exit(1)

# Database connection
DB_URL = "postgresql://postgres:FZHYAmmFYRIFaiZSwiDFJsZLHPtSIWnx@caboose.proxy.rlwy.net:44462/railway"

print("\n" + "="*60)
print("🔧 Fix Admin Password")
print("="*60)

try:
    # Parse connection string
    db_url = DB_URL
    if db_url.startswith("postgresql://"):
        db_url = db_url[13:]
    elif db_url.startswith("postgres://"):
        db_url = db_url[11:]
    
    creds, host_db = db_url.split("@")
    username, password = creds.split(":")
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
    
    conn = psycopg2.connect(
        host=host,
        port=port,
        database=database,
        user=username,
        password=password
    )
    
    cursor = conn.cursor()
    
    # Check if admin user exists
    cursor.execute("""
        SELECT id, email, is_active
        FROM users
        WHERE email = 'admin@coredent.com'
    """)
    
    result = cursor.fetchone()
    
    if not result:
        print("\n❌ Admin user not found!")
        print("\nCreating admin user...")
        
        # Create practice first
        from uuid import uuid4
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
        
        # Create admin user
        user_id = str(uuid4())
        password_hash = "$2b$12$R9h7cIPz0gi.URNNX3kh2OPST9/PgBBkqq8Kj7KqkL1p8T9m.Yvva"
        
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
        print("✅ Admin user created!")
        
    else:
        user_id, email, is_active = result
        print(f"\n✅ Admin user found: {email}")
        print(f"   Active: {is_active}")
        
        # Update password hash
        print("\n🔐 Updating password hash...")
        password_hash = "$2b$12$R9h7cIPz0gi.URNNX3kh2OPST9/PgBBkqq8Kj7KqkL1p8T9m.Yvva"
        
        cursor.execute("""
            UPDATE users
            SET password_hash = %s
            WHERE email = 'admin@coredent.com'
        """, (password_hash,))
        
        conn.commit()
        print("✅ Password hash updated!")
    
    cursor.close()
    conn.close()
    
    print("\n" + "="*60)
    print("✅ SUCCESS!")
    print("="*60)
    print("\nYou can now login with:")
    print("   Email: admin@coredent.com")
    print("   Password: Admin123!")
    print("\n⚠️  IMPORTANT: Change the password after first login!")
    print("="*60 + "\n")
    
except Exception as e:
    print(f"\n❌ Error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
