#!/usr/bin/env python3
"""
Verify Admin Password Hash
Check if the password hash in database matches Admin123!
"""

import sys

try:
    import psycopg2
    import bcrypt
except ImportError:
    print("❌ Required packages not installed")
    print("\nInstall them with:")
    print("  pip install psycopg2-binary bcrypt")
    sys.exit(1)

# Get connection string from user
print("\n" + "="*60)
print("🔍 Verify Admin Password")
print("="*60)

db_url = input("\nEnter Railway PostgreSQL URL (postgresql://...): ").strip()

if not db_url:
    print("❌ No database URL provided")
    sys.exit(1)

# Parse connection string
try:
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
    
    # Get admin user
    cursor.execute("""
        SELECT id, email, password_hash, is_active, role
        FROM users
        WHERE email = 'admin@coredent.com'
    """)
    
    result = cursor.fetchone()
    
    if not result:
        print("\n❌ Admin user not found in database!")
        print("\nRun create_test_user_simple.py to create the admin user.")
        sys.exit(1)
    
    user_id, email, password_hash, is_active, role = result
    
    print(f"\n✅ Admin user found:")
    print(f"   ID: {user_id}")
    print(f"   Email: {email}")
    print(f"   Active: {is_active}")
    print(f"   Role: {role}")
    
    # Test password
    test_password = "Admin123!"
    print(f"\n🔐 Testing password: {test_password}")
    
    # Verify password
    if bcrypt.checkpw(test_password.encode('utf-8'), password_hash.encode('utf-8')):
        print("✅ Password matches!")
        print("\nYou should be able to login with:")
        print(f"   Email: {email}")
        print(f"   Password: {test_password}")
    else:
        print("❌ Password does NOT match!")
        print("\nThe password hash in the database doesn't match 'Admin123!'")
        print("\nOptions:")
        print("1. Try a different password")
        print("2. Reset the admin user by running create_test_user_simple.py again")
        print("   (Delete the user first or use a different email)")
    
    cursor.close()
    conn.close()
    
except Exception as e:
    print(f"\n❌ Error: {e}")
    sys.exit(1)

print("\n" + "="*60 + "\n")
