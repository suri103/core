import requests
import json
import jwt

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
    access_token = data.get("access_token")
    refresh_token = data.get("refresh_token")
    
    print(f"\nAccess Token: {access_token[:50]}...")
    print(f"Refresh Token: {refresh_token[:50]}...")
    
    # Decode access token
    print("\n=== ACCESS TOKEN PAYLOAD ===")
    access_decoded = jwt.decode(access_token, options={"verify_signature": False})
    print(json.dumps(access_decoded, indent=2))
    
    # Test /auth/me with access token
    print("\n=== TESTING /auth/me ===")
    me_response = requests.get(
        "http://localhost:8080/api/v1/auth/me",
        headers={"Authorization": f"Bearer {access_token}"}
    )
    
    print(f"Me Status: {me_response.status_code}")
    print(f"Me Response: {me_response.text}")
else:
    print(f"Login failed: {response.text}")