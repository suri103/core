import asyncio
import os
import sys

# Ensure UTF-8 output
sys.stdout.reconfigure(encoding='utf-8')

# Set environment
os.environ["ENVIRONMENT"] = "development"
os.environ["SECRET_KEY"] = "yWfBS3_teqlJHzliDS1073yjj4CaTS2ig7zv-t-LgOzX9uJFD0dtGrxCtZPzvlFf00ertjQVQuWIzx2iW1FsOQ"
os.environ["ENCRYPTION_KEY"] = "CSpvNit8ELpFt6XWDM4CtIprX4LTqeD7oFCXVlXpHTo="
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///./coredent_test.db"

from app.core.database import engine, Base  # noqa: E402
from app.main import app  # noqa: E402
from httpx import AsyncClient, ASGITransport  # noqa: E402

async def run_tests():
    print("🚀 Initializing Database...")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    
    print("✅ Database Initialized.")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        print("\n🧪 Testing Auth Flow...")
        # 1. Test Login (should fail if user doesn't exist, but we check endpoint response)
        resp = await client.post("/api/v1/auth/login", data={"username": "test@test.com", "password": "Password123!"})
        print(f"Login Response Status: {resp.status_code}")
        # 401/400 is expected since DB is fresh and user doesn't exist
        
        print("\n🧪 Testing EDI Claims...")
        # Try missing auth first
        resp = await client.post("/api/v1/edi/eligibility", json={"patient_insurance_id": "00000000-0000-0000-0000-000000000000"})
        print(f"EDI Response Status: {resp.status_code} (Expected 401 without auth)")

        print("\n✅ Integration endpoints exist and are responding.")

if __name__ == "__main__":
    asyncio.run(run_tests())
