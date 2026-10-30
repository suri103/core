import sqlite3

conn = sqlite3.connect('coredent-api/coredent_dev.db')
cursor = conn.cursor()

# Get all tables
cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;")
tables = cursor.fetchall()
print('=== DATABASE TABLES ===')
for table in tables:
    print(f'  - {table[0]}')

# Check practices table structure
print('\n=== PRACTICES TABLE STRUCTURE ===')
cursor.execute('PRAGMA table_info(practices);')
columns = cursor.fetchall()
for col in columns:
    print(f'  {col[1]}: {col[2]}')

# Check if admin user exists
print('\n=== ADMIN USER CHECK ===')
cursor.execute('SELECT id, email, role, is_active FROM users WHERE email = ?;', ('admin@coredent.com',))
admin = cursor.fetchone()
if admin:
    print(f'  Email: {admin[1]}')
    print(f'  Role: {admin[2]}')
    print(f'  Active: {admin[3]}')
else:
    print('  No admin user found')

# Check practice
print('\n=== PRACTICE CHECK ===')
cursor.execute('SELECT id, name, is_active FROM practices LIMIT 1;')
practice = cursor.fetchone()
if practice:
    print(f'  ID: {practice[0]}')
    print(f'  Name: {practice[1]}')
    print(f'  Active: {practice[2]}')
else:
    print('  No practices found')

conn.close()
