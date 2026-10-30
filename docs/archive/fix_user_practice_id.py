import sqlite3

conn = sqlite3.connect('coredent-api/coredent_dev.db')
cursor = conn.cursor()

# Get the practice ID
cursor.execute("SELECT id, name FROM practices")
practice = cursor.fetchone()

if not practice:
    print("✗ No practice found!")
    conn.close()
    exit(1)

practice_id = practice[0]
practice_name = practice[1]
print(f"Found practice: {practice_name} (ID: {practice_id})")

# Get the admin user
cursor.execute("SELECT id, email, practice_id FROM users WHERE email = 'admin@coredent.com'")
user = cursor.fetchone()

if not user:
    print("✗ Admin user not found!")
    conn.close()
    exit(1)

user_id = user[0]
user_email = user[1]
current_practice_id = user[2]

print(f"\nAdmin user: {user_email}")
print(f"Current practice_id: {current_practice_id}")

if current_practice_id == practice_id:
    print("✓ User already has correct practice_id")
else:
    # Update the user's practice_id
    cursor.execute("UPDATE users SET practice_id = ? WHERE id = ?", (practice_id, user_id))
    conn.commit()
    print(f"✓ Updated user practice_id to: {practice_id}")

conn.close()
print("\n✓ Done!")
