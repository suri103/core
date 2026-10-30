#!/usr/bin/env python3
"""
Generate a secure SECRET_KEY for Railway deployment
Run this and copy the output to Railway environment variables
"""

import secrets

if __name__ == "__main__":
    print("=" * 60)
    print("SECRET_KEY Generator for Railway")
    print("=" * 60)
    print()
    print("Copy this value and add it to Railway Variables:")
    print()
    secret_key = secrets.token_urlsafe(32)
    print(secret_key)
    print()
    print("=" * 60)
    print()
    print("This key is:", len(secret_key), "characters long")
    print("Minimum required: 32 characters")
    print()
    if len(secret_key) >= 32:
        print("✓ This key is valid!")
    else:
        print("✗ This key is too short!")
    print()
    print("=" * 60)
