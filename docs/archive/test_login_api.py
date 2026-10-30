#!/usr/bin/env python3
"""
Test Login API Directly
"""

import requests
import json

API_URL = "https://coredentist-production.up.railway.app/api/v1"

print("\n" + "="*60)
print("🧪 Testing Login API")
print("="*60)

# Test login
print("\n1. Testing login endpoint...")
login_data = {
    "email": "admin@coredent.com",
    "password": "Admin123!"
}

try:
    response = requests.post(
        f"{API_URL}/auth/login",
        json=login_data,
        headers={
            "Content-Type": "application/json",
            "Origin": "https://respectful-strength-production-ef28.up.railway.app"
        }
    )
    
    print(f"   Status Code: {response.status_code}")
    print(f"   Headers: {dict(response.headers)}")
    
    if response.status_code == 200:
        print("   ✅ Login successful!")
        data = response.json()
        print(f"   Response: {json.dumps(data, indent=2)}")
    else:
        print(f"   ❌ Login failed!")
        print(f"   Response: {response.text}")
        
except Exception as e:
    print(f"   ❌ Error: {e}")

print("\n" + "="*60 + "\n")
