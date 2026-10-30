import requests
import json

BASE_URL = "http://localhost:8080/api/v1"

# Login first
login_response = requests.post(
    f"{BASE_URL}/auth/login",
    json={
        "email": "admin@coredent.com",
        "password": "Admin123!@#"
    }
)

login_data = login_response.json()
access_token = login_data.get("access_token")

# Test /auth/me
headers = {"Authorization": f"Bearer {access_token}"}
me_response = requests.get(f"{BASE_URL}/auth/me", headers=headers)

print("Raw response:")
print(json.dumps(me_response.json(), indent=2))
