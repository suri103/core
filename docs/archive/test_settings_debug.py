import requests
import json

BASE_URL = "http://localhost:8080/api/v1"

# Login first
print("1. Logging in...")
login_response = requests.post(
    f"{BASE_URL}/auth/login",
    json={
        "email": "admin@coredent.com",
        "password": "Admin123!@#"
    }
)

if login_response.status_code != 200:
    print(f"✗ Login failed: {login_response.status_code}")
    print(login_response.text)
    exit(1)

login_data = login_response.json()
access_token = login_data.get("access_token")
print(f"✓ Login successful")
print(f"Token: {access_token[:50]}...")

# Test /auth/me to see user data
print("\n2. Testing /auth/me endpoint...")
headers = {"Authorization": f"Bearer {access_token}"}
me_response = requests.get(f"{BASE_URL}/auth/me", headers=headers)

print(f"Status: {me_response.status_code}")
if me_response.status_code == 200:
    user_data = me_response.json()
    print("✓ User data loaded")
    print(f"  - Email: {user_data.get('email')}")
    print(f"  - Role: {user_data.get('role')}")
    print(f"  - Practice ID: {user_data.get('practiceId')}")
    print(f"  - Practice Name: {user_data.get('practiceName')}")
else:
    print(f"✗ Failed: {me_response.text}")
    exit(1)

# Test billing settings endpoint
print("\n3. Testing billing settings endpoint...")
billing_response = requests.get(f"{BASE_URL}/settings/billing", headers=headers)

print(f"Status: {billing_response.status_code}")
print(f"Response: {billing_response.text}")
