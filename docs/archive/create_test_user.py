#!/usr/bin/env python3
"""
Create Test Admin User - Standalone Script
This script creates a test admin user directly in the Railway PostgreSQL database
"""

import asyncio
import sys
from uuid import uuid4
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text

# Railway PostgreSQL connection details
# Get these from Railway dashboard → PostgreSQL service → Connect
DATABASE_URL = input("Enter your Railway PostgreSQL connection string (postgresql://...): ").strip()

if not DATABASE_URL:
    print("❌ No database URL provided")
    sys.exit(1)

# Convert to async URL
if "postgresql://" in DATABASE_URL:
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://")

print(f"\n🔗 Connecting to database...")
print(f"URL: {DATABASE_URL[:50]}...")


async def create_admin():
    """Create admin user and practice"""
    try:
        # Create async engine
        engine = create_async_engine(DATABASE_URL, echo=False)
        
        # Create session
        async_session = sessionmaker(
            engine, class_=AsyncSession, expire_on_commit=False
        )
        
        async with async_session() as session:
            print("\n📝 Creating practice...")
            
            # Create practice
            practice_id = str(uuid4())
            await session.execute(
                text("""
                    INSERT INTO practice (
                        id, name, email, phone,
                        address_street, address_city, address_state, address_zip,
                        timezone, currency, created_at, updated_at
                    ) VALUES (
                        :id, :name, :email, :phone,
                        :street, :city, :state, :zip,
                        :tz, :currency, NOW(), NOW()
                    )
                """),
                {
                    "id": practice_id,
                    "name": "Demo Dental Practice",
                    "email": "info@demodental.com",
                    "phone": "555-0123",
                    "street": "123 Main Street",
                    "city": "Springfield",
                    "state": "IL",
                    "zip": "62701",
                    "tz": "America/Chicago",
                    "currency": "USD",
                }
            )
            
            print("✅ Practice created")
            print("\n👤 Creating admin user...")
            
            # Password hash for "Admin123!" (bcrypt)
            password_hash = "$2b$12$R9h7cIPz0gi.URNNX3kh2OPST9/PgBBkqq8Kj7KqkL1p8T9m.Yvva"
            
            # Create admin user
            user_id = str(uuid4())
            await session.execute(
                text("""
                    INSERT INTO "user" (
                        id, email, password_hash, first_name, last_name,
                        role, practice_id, is_active, created_at, updated_at
                    ) VALUES (
                        :id, :email, :password_hash, :first_name, :last_name,
                        :role, :practice_id, :is_active, NOW(), NOW()
                    )
                """),
                {
                    "id": user_id,
                    "email": "admin@coredent.com",
                    "password_hash": password_hash,
                    "first_name": "Admin",
                    "last_name": "User",
                    "role": "owner",
                    "practice_id": practice_id,
                    "is_active": True,
                }
            )
            
            await session.commit()
            
            print("✅ Admin user created")
            print("\n" + "="*60)
            print("✅ SUCCESS!")
            print("="*60)
            print(f"\nPractice: Demo Dental Practice")
            print(f"Practice ID: {practice_id}")
            print(f"\nAdmin Email: admin@coredent.com")
            print(f"Admin Password: Admin123!")
            print(f"Admin ID: {user_id}")
            print("\n⚠️  IMPORTANT: Change the password after first login!")
            print("="*60 + "\n")
        
        await engine.dispose()
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        print("\nTroubleshooting:")
        print("1. Check that the database URL is correct")
        print("2. Make sure you can connect to Railway PostgreSQL")
        print("3. Verify the tables exist (run migrations first)")
        sys.exit(1)


if __name__ == "__main__":
    print("\n🚀 Creating admin user...\n")
    asyncio.run(create_admin())
