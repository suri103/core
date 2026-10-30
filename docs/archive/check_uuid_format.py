import sqlite3
from uuid import UUID

conn = sqlite3.connect('coredent-api/coredent_dev.db')
cursor = conn.cursor()

# Check the user ID format in the database
cursor.execute('SELECT id, email FROM users WHERE email = ?;', ('admin@coredent.com',))
user = cursor.fetchone()

if user:
    db_user_id = user[0]
    print(f"Database user ID: {db_user_id}")
    print(f"Database user ID type: {type(db_user_id)}")
    print(f"Database user email: {user[1]}")
    
    # Try to query with the UUID string
    print("\n=== Testing query with UUID string ===")
    cursor.execute('SELECT id, email FROM users WHERE id = ?;', (db_user_id,))
    result = cursor.fetchone()
    if result:
        print(f"Found user: {result[1]}")
    else:
        print("User not found with string ID")
    
    # Try with UUID object
    print("\n=== Testing query with UUID object ===")
    uuid_obj = UUID(db_user_id)
    cursor.execute('SELECT id, email FROM users WHERE id = ?;', (str(uuid_obj),))
    result = cursor.fetchone()
    if result:
        print(f"Found user: {result[1]}")
    else:
        print("User not found with UUID object")
    
    # Check the actual bytes stored
    print("\n=== Checking ID format ===")
    cursor.execute('SELECT typeof(id), id FROM users WHERE email = ?;', ('admin@coredent.com',))
    typeof_result = cursor.fetchone()
    print(f"ID type in DB: {typeof_result[0]}")
    print(f"ID value: {typeof_result[1]}")

conn.close()