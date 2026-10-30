import requests

# Test login
print('Testing login...')
resp = requests.post('http://localhost:8080/api/v1/auth/login', json={
    'email': 'admin@coredent.com',
    'password': 'Admin123!@#'
})
print(f'Login status: {resp.status_code}')
if resp.status_code == 200:
    data = resp.json()
    token = data.get('access_token', 'NO TOKEN')
    print(f'Got token: {token[:20]}...')
    
    # Test /auth/me
    print('\nTesting /auth/me...')
    me_resp = requests.get('http://localhost:8080/api/v1/auth/me', 
        headers={'Authorization': f'Bearer {token}'},
        cookies=resp.cookies
    )
    print(f'/auth/me status: {me_resp.status_code}')
    if me_resp.status_code == 200:
        user = me_resp.json()
        print(f'User: {user.get("email")} - Role: {user.get("role")}')
    else:
        print('Error:', me_resp.text[:200])
else:
    print('Login failed:', resp.text[:200])
