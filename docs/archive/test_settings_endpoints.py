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

# Test billing settings endpoint
print("\n2. Testing billing settings endpoint...")
headers = {"Authorization": f"Bearer {access_token}"}
billing_response = requests.get(f"{BASE_URL}/settings/billing", headers=headers)

print(f"Status: {billing_response.status_code}")
if billing_response.status_code == 200:
    print("✓ Billing settings loaded successfully")
    print(json.dumps(billing_response.json(), indent=2))
else:
    print(f"✗ Failed to load billing settings")
    print(billing_response.text)

# Test clinic settings endpoint
print("\n3. Testing clinic settings endpoint...")
clinic_response = requests.get(f"{BASE_URL}/clinic/settings", headers=headers)

print(f"Status: {clinic_response.status_code}")
if clinic_response.status_code == 200:
    print("✓ Clinic settings loaded successfully")
    data = clinic_response.json()
    print(f"  - Name: {data.get('name')}")
    print(f"  - Appointment types: {len(data.get('appointmentTypes', []))} types")
    print(f"  - Chairs: {len(data.get('chairs', []))} chairs")
    print(f"  - Working hours: {len(data.get('workingHours', {}))} days")
else:
    print(f"✗ Failed to load clinic settings")
    print(clinic_response.text)

print("\n✓ All tests complete!")
