#!/usr/bin/env python3
"""
Create database tables directly using SQL
This bypasses alembic and creates tables directly on Railway
"""

import psycopg2
import sys

print("\n" + "="*70)
print("🚀 Create Database Tables on Railway")
print("="*70)

db_url = input("\nEnter Railway PostgreSQL public URL (postgresql://...): ").strip()

if not db_url:
    print("❌ No URL provided")
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
    
    print(f"\n🔗 Connecting to {host}:{port}/{database}...")
    
    conn = psycopg2.connect(
        host=host,
        port=port,
        database=database,
        user=username,
        password=password
    )
    
    cursor = conn.cursor()
    
    print("📝 Creating tables...")
    
    # Read and execute the schema SQL
    with open("coredent-api/db_schema.sql", "r") as f:
        sql = f.read()
    
    # Execute the SQL
    cursor.execute(sql)
    conn.commit()
    
    print("✅ Tables created successfully!")
    
    # Verify tables exist
    cursor.execute("""
        SELECT table_name FROM information_schema.tables 
        WHERE table_schema = 'public'
    """)
    
    tables = cursor.fetchall()
    print(f"\n✅ Created {len(tables)} tables:")
    for table in tables:
        print(f"   - {table[0]}")
    
    cursor.close()
    conn.close()
    
    print("\n" + "="*70)
    print("✅ SUCCESS! All tables created.")
    print("="*70)
    print("\nNow you can run:")
    print("  python create_test_user_simple.py")
    print("="*70 + "\n")
    
except Exception as e:
    print(f"\n❌ Error: {e}")
    sys.exit(1)
