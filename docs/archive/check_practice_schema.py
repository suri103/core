import sqlite3

conn = sqlite3.connect('coredent-api/coredent_dev.db')
cursor = conn.cursor()

# Get table schema
cursor.execute("PRAGMA table_info(practices)")
columns = cursor.fetchall()

print("Practices table columns:")
for col in columns:
    print(f"  {col[1]} ({col[2]})")

conn.close()
