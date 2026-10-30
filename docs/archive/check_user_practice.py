import sqlite3

conn = sqlite3.connect('coredent-api/coredent_dev.db')
cursor = conn.cursor()

# Get user data
cursor.execute("SELECT id, email, practice_id, role, is_active FROM users WHERE email = 'admin@coredent.com'")
user = cursor.fetchone()

if user:
    print(f"User ID: {user[0]}")
    print(f"Email: {user[1]}")
    print(f"Practice ID: {user[2]}")
    print(f"Role: {user[3]}")
    print(f"Is Active: {user[4]}")
    
    # Get practice data
    if user[2]:
        cursor.execute("SELECT id, name, is_active FROM practices WHERE id = ?", (user[2],))
        practice = cursor.fetchone()
        if practice:
            print(f"\nPractice ID: {practice[0]}")
            print(f"Practice Name: {practice[1]}")
            print(f"Practice Active: {practice[2]}")
        else:
            print(f"\n✗ Practice not found with ID: {user[2]}")
    else:
        print("\n✗ User has no practice_id!")
else:
    print("✗ User not found!")

conn.close()
