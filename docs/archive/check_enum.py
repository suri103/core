#!/usr/bin/env python3
"""Check what enum values exist in PostgreSQL"""

import psycopg2

db_url = 'postgresql://postgres:FZHYAmmFYRIFaiZSwiDFJsZLHPtSIWnx@caboose.proxy.rlwy.net:44462/railway'

# Parse connection string
db_url = db_url[13:]  # Remove postgresql://
creds, host_db = db_url.split('@')
username, password = creds.split(':')
host_port, database = host_db.split('/')
host, port = host_port.split(':')
port = int(port)

conn = psycopg2.connect(
    host=host,
    port=port,
    database=database,
    user=username,
    password=password
)

cursor = conn.cursor()

# Check what enum values exist
cursor.execute("""
    SELECT enumlabel FROM pg_enum 
    WHERE enumtypid = (SELECT oid FROM pg_type WHERE typname = 'userrole')
    ORDER BY enumsortorder
""")

rows = cursor.fetchall()
print('Enum values in PostgreSQL:')
if rows:
    for row in rows:
        print(f'  - {row[0]}')
else:
    print('  (no enum values found)')

# Also check if the enum type exists
cursor.execute("""
    SELECT typname FROM pg_type WHERE typname = 'userrole'
""")
enum_exists = cursor.fetchone()
print(f'\nEnum type "userrole" exists: {bool(enum_exists)}')

cursor.close()
conn.close()
