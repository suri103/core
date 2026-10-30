import sqlite3

conn = sqlite3.connect('coredent-api/coredent_dev.db')
cursor = conn.cursor()

# Update role to lowercase
cursor.execute("UPDATE users SET role = 'admin' WHERE role = 'ADMIN'")
conn.commit()

print(f"✓ Updated {cursor.rowcount} user(s) to lowercase role")

# Verify
cursor.execute("SELECT email, role FROM users")
users = cursor.fetchall()
for user in users:
    print(f"  - {user[0]}: {user[1]}")

conn.close()
