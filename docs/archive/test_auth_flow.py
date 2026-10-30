import requests
import json

# Login
login_data = {
    "email": "admin@coredent.com",
    "password": "Admin123!@#"
}

print("=== TESTING LOGIN ===")
response = requests.post(
    "http://localhost:8080/api/v1/auth/login",
    json=login_data,
    headers={"Content-Type": "application/json"}
)

print(f"Login Status: {response.status_code}")
if response.status_code == 200:
    data = response.json()
    token = data.get("access_token")
    print(f"Token received: {token[:30]}...")
    
    # Test /auth/me
    print("\n=== TESTING /auth/me ===")
    me_response = requests.get(
        "http://localhost:8080/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"}
    )
    
    print(f"Me Status: {me_response.status_code}")
    print(f"Me Response: {me_response.text}")
else:
    print(f"Login failed: {response.text}")