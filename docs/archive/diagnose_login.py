#!/usr/bin/env python3
"""
Diagnose login issues by testing the auth endpoint directly
"""

import requests
import json
import sys

# Configuration
BACKEND_URL = input("Enter your Railway backend URL (e.g., https://your-app.railway.app): ").strip()
if not BACKEND_URL:
    print("Error: Backend URL is required")
    sys.exit(1)

# Remove trailing slash
BACKEND_URL = BACKEND_URL.rstrip('/')

print(f"\n🔍 Testing backend: {BACKEND_URL}")
print("=" * 60)

# Test 1: Health check
print("\n1️⃣ Testing health endpoint...")
try:
    response = requests.get(f"{BACKEND_URL}/health", timeout=10)
    print(f"   Status: {response.status_code}")
    if response.status_code == 200:
        print("   ✅ Backend is online")
    else:
        print(f"   ❌ Backend returned: {response.text}")
except Exception as e:
    print(f"   ❌ Error: {e}")
    print("\n⚠️  Backend is not accessible. Check Railway deployment logs.")
    sys.exit(1)

# Test 2: Login endpoint
print("\n2️⃣ Testing login endpoint...")
email = input("Enter email (default: admin@coredent.com): ").strip() or "admin@coredent.com"
password = input("Enter password (default: Admin123!@#): ").strip() or "Admin123!@#"

try:
    response = requests.post(
        f"{BACKEND_URL}/api/v1/auth/login",
        json={"email": email, "password": password},
        headers={"Content-Type": "application/json"},
        timeout=10
    )
    
    print(f"   Status: {response.status_code}")
    
    if response.status_code == 200:
        data = response.json()
        print("   ✅ Login successful!")
        print(f"\n   Response:")
        print(f"   - access_token: {data.get('access_token', 'N/A')[:50]}...")
        print(f"   - refresh_token: {data.get('refresh_token', 'N/A')[:50]}...")
        print(f"   - token_type: {data.get('token_type', 'N/A')}")
        print(f"   - expires_in: {data.get('expires_in', 'N/A')} seconds")
        print(f"   - csrf_token: {data.get('csrf_token', 'N/A')[:50]}...")
        
        # Test 3: Get current user with token
        print("\n3️⃣ Testing /auth/me endpoint with token...")
        access_token = data.get('access_token')
        if access_token:
            me_response = requests.get(
                f"{BACKEND_URL}/api/v1/auth/me",
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Content-Type": "application/json"
                },
                timeout=10
            )
            print(f"   Status: {me_response.status_code}")
            if me_response.status_code == 200:
                user_data = me_response.json()
                print("   ✅ User data retrieved!")
                print(f"\n   User:")
                print(f"   - ID: {user_data.get('id', 'N/A')}")
                print(f"   - Email: {user_data.get('email', 'N/A')}")
                print(f"   - Name: {user_data.get('first_name', 'N/A')} {user_data.get('last_name', 'N/A')}")
                print(f"   - Role: {user_data.get('role', 'N/A')}")
                print(f"   - Practice: {user_data.get('practice_name', 'N/A')}")
            else:
                print(f"   ❌ Failed to get user data: {me_response.text}")
        
        print("\n" + "=" * 60)
        print("✅ DIAGNOSIS: Backend authentication is working correctly!")
        print("\nIf frontend login is failing, check:")
        print("1. Frontend VITE_API_BASE_URL environment variable")
        print("2. CORS configuration in backend")
        print("3. Browser console for errors")
        print("4. Network tab in browser DevTools")
        
    elif response.status_code == 401:
        print("   ❌ Login failed: Invalid credentials")
        print(f"   Response: {response.text}")
        print("\n⚠️  Check if user exists in database or password is correct")
        
    elif response.status_code == 429:
        print("   ❌ Login failed: Too many attempts (rate limited)")
        print(f"   Response: {response.text}")
        print("\n⚠️  Account may be locked. Wait 15 minutes or reset in database")
        
    else:
        print(f"   ❌ Login failed with status {response.status_code}")
        print(f"   Response: {response.text}")
        
except Exception as e:
    print(f"   ❌ Error: {e}")
    print("\n⚠️  Unable to test login endpoint")

print("\n" + "=" * 60)
