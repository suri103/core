import requests
import json

# Test login
login_url = "http://localhost:8080/api/v1/auth/login"
login_data = {
    "email": "admin@coredent.com",
    "password": "Admin123!@#"
}

print("Testing login...")
response = requests.post(login_url, json=login_data)
print(f"Status: {response.status_code}")

if response.status_code == 200:
    data = response.json()
    print(f"Login successful!")
    
    # Get access token
    access_token = data.get("access_token")
    
    # Test /me endpoint
    me_url = "http://localhost:8080/api/v1/auth/me"
    headers = {"Authorization": f"Bearer {access_token}"}
    
    print("\nTesting /me endpoint...")
    me_response = requests.get(me_url, headers=headers)
    print(f"Status: {me_response.status_code}")
    
    if me_response.status_code == 200:
        user_data = me_response.json()
        print(f"\nUser data:")
        print(json.dumps(user_data, indent=2))
        print(f"\nRole value: '{user_data.get('role')}'")
        print(f"Role type: {type(user_data.get('role'))}")
    else:
        print(f"Error: {me_response.text}")
else:
    print(f"Login failed: {response.text}")
