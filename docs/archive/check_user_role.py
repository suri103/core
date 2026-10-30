import sqlite3

conn = sqlite3.connect('coredent-api/coredent_dev.db')
cursor = conn.cursor()
result = cursor.execute('SELECT email, role FROM users WHERE email = ?', ('admin@coredent.com',)).fetchone()
if result:
    print(f'Email: {result[0]}')
    print(f'Role: {result[1]}')
    print(f'Role type: {type(result[1])}')
else:
    print('User not found')
conn.close()
