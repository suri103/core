#!/usr/bin/env python3
"""
Update Admin Password with Correct Hash
"""

import sys

try:
    import psycopg2
    import bcrypt
except ImportError:
    print("❌ Required packages not installed")
    print("\nInstall: pip install psycopg2-binary bcrypt")
    sys.exit(1)

DB_URL = "postgresql://postgres:FZHYAmmFYRIFaiZSwiDFJsZLHPtSIWnx@caboose.proxy.rlwy.net:44462/railway"

print("\n" + "="*60)
print("🔧 Update Admin Password (Correct Hash)")
print("="*60)

try:
    # Parse connection
    db_url = DB_URL[13:] if DB_URL.startswith("postgresql://") else DB_URL[11:]
    creds, host_db = db_url.split("@")
    username, password = creds.split(":")
    host_port, database = host_db.split("/")
    host, port = (host_port.split(":")[0], int(host_port.split(":")[1])) if ":" in host_port else (host_port, 5432)
    
    print(f"\n🔗 Connecting...")
    conn = psycopg2.connect(host=host, port=port, database=database, user=username, password=password)
    cursor = conn.cursor()
    
    # Generate correct hash for Admin123!
    test_password = "Admin123!"
    print(f"\n🔐 Generating hash for: '{test_password}'")
    correct_hash = bcrypt.hashpw(test_password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    print(f"   Hash: {correct_hash[:50]}...")
    
    # Update database
    print(f"\n📝 Updating database...")
    cursor.execute("""
        UPDATE users
        SET password_hash = %s
        WHERE email = 'admin@coredent.com'
    """, (correct_hash,))
    
    conn.commit()
    
    # Verify
    cursor.execute("SELECT password_hash FROM users WHERE email = 'admin@coredent.com'")
    new_hash = cursor.fetchone()[0]
    
    if bcrypt.checkpw(test_password.encode('utf-8'), new_hash.encode('utf-8')):
        print("✅ Password hash updated and verified!")
    else:
        print("❌ Verification failed!")
    
    cursor.close()
    conn.close()
    
    print("\n" + "="*60)
    print("✅ SUCCESS!")
    print("="*60)
    print("\nLogin credentials:")
    print("   Email: admin@coredent.com")
    print("   Password: Admin123!")
    print("="*60 + "\n")
    
except Exception as e:
    print(f"\n❌ Error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
