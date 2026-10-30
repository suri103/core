import sqlite3

conn = sqlite3.connect('coredent-api/coredent_dev.db')
cursor = conn.cursor()

# Get all tables
cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
tables = cursor.fetchall()

print("All tables:")
for table in tables:
    print(f"  - {table[0]}")

# Check if chairs and appointment_types tables exist
if ('chairs',) in tables:
    print("\n✓ chairs table exists")
else:
    print("\n✗ chairs table does NOT exist")

if ('appointment_types',) in tables:
    print("✓ appointment_types table exists")
else:
    print("✗ appointment_types table does NOT exist")

conn.close()
