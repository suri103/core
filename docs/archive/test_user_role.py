import sqlite3

conn = sqlite3.connect('coredent-api/coredent_dev.db')
cursor = conn.cursor()

cursor.execute("SELECT email, role FROM users WHERE email = 'admin@coredent.com'")
user = cursor.fetchone()

print(f"Email: {user[0]}")
print(f"Role: {user[1]}")
print(f"Role type: {type(user[1])}")

conn.close()
