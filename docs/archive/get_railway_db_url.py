#!/usr/bin/env python3
"""
Get DATABASE_URL from Railway backend service
This script helps you retrieve the database connection string
"""

print("\n" + "="*70)
print("🚀 Get Railway Database URL")
print("="*70)

print("\nTo get your DATABASE_URL from Railway:")
print("\n1. Go to: https://railway.app/dashboard")
print("2. Click on 'practical-dream' project")
print("3. Click on 'coredentist' (backend service)")
print("4. Go to 'Variables' tab")
print("5. Look for 'DATABASE_URL' variable")
print("6. Copy the entire value (starts with postgresql://)")
print("\nAlternatively:")
print("1. Click on PostgreSQL service")
print("2. Go to 'Connect' tab")
print("3. Copy the 'Private URL' (for internal connections)")
print("   Format: postgresql://postgres:PASSWORD@postgres.railway.internal:5432/railway")
print("\n" + "="*70)

db_url = input("\nPaste your DATABASE_URL here: ").strip()

if not db_url:
    print("❌ No URL provided")
    exit(1)

if not db_url.startswith("postgresql://"):
    print("❌ Invalid URL format. Must start with 'postgresql://'")
    exit(1)

print("\n✅ URL received!")
print(f"\nYour DATABASE_URL:\n{db_url}")
print("\n" + "="*70)
print("\nNow run:")
print(f"  python create_test_user_simple.py")
print("\nAnd paste this URL when prompted.")
print("="*70 + "\n")
