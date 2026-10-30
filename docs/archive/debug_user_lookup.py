import sqlite3
from uuid import UUID

conn = sqlite3.connect('coredent-api/coredent_dev.db')
cursor = conn.cursor()

# Get the admin user
cursor.execute('SELECT id, email, role, is_active, practice_id FROM users WHERE email = ?;', ('admin@coredent.com',))
user = cursor.fetchone()

if user:
    user_id, email, role, is_active, practice_id = user
    print(f"User ID: {user_id}")
    print(f"Email: {email}")
    print(f"Role: {role}")
    print(f"Is Active: {is_active}")
    print(f"Practice ID: {practice_id}")
    
    # Check if practice exists
    if practice_id:
        cursor.execute('SELECT id, name, is_active FROM practices WHERE id = ?;', (practice_id,))
        practice = cursor.fetchone()
        if practice:
            print(f"\nPractice found:")
            print(f"  ID: {practice[0]}")
            print(f"  Name: {practice[1]}")
            print(f"  Is Active: {practice[2]}")
        else:
            print(f"\nPractice NOT found for ID: {practice_id}")
    else:
        print("\nNo practice_id assigned to user")
else:
    print("Admin user not found")

conn.close()
