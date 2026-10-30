#!/usr/bin/env python3
"""
Check what enum values are valid for the userrole type
"""

import psycopg2
import sys

db_url = input("Enter Railway PostgreSQL public URL (postgresql://...): ").strip()

if not db_url:
    print("❌ No URL provided")
    sys.exit(1)

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
    
    conn = psycopg2.connect(
        host=host,
        port=port,
        database=database,
        user=username,
        password=password
    )
    
    cursor = conn.cursor()
    
    # Check enum values
    cursor.execute("""
        SELECT enumlabel FROM pg_enum 
        WHERE enumtypid = (SELECT oid FROM pg_type WHERE typname = 'userrole')
        ORDER BY enumsortorder
    """)
    
    values = cursor.fetchall()
    
    if values:
        print("\n✅ Valid userrole enum values:")
        for val in values:
            print(f"   - {val[0]}")
    else:
        print("\n❌ No enum values found for userrole")
    
    cursor.close()
    conn.close()
    
except Exception as e:
    print(f"❌ Error: {e}")
    sys.exit(1)
