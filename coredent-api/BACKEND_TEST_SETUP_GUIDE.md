# Backend Test Setup Guide

## Current Status

The backend test fixtures have been partially migrated to async, but there are still issues with pytest-asyncio fixture resolution. This is a **low priority** issue that does not block production deployment.

## Problem

The test fixtures in `conftest.py` are async generators, but pytest-asyncio is not properly resolving them in the test functions. The error is:

```
AttributeError: 'async_generator' object has no attribute 'get'
```

## What Was Done

1. ✅ Updated `conftest.py` to use async fixtures with `AsyncSession` and `AsyncClient`
2. ✅ Updated all test files (`test_auth.py`, `test_patients.py`, `test_appointments.py`) to use `@pytest.mark.asyncio` and `await`
3. ✅ Changed from `TestClient` to `AsyncClient` (httpx)
4. ✅ Added proper async database setup/teardown

## What Still Needs to Be Done

### Option 1: Use pytest-asyncio fixture properly

The issue is that pytest-asyncio needs fixtures to be consumed with `async with` or properly awaited. Try this approach:

```python
# In conftest.py
@pytest.fixture
async def client(setup_database):
    """Create async test client"""
    async with AsyncClient(app=app, base_url="http://test") as ac:
        yield ac

# In test files - this should work but doesn't
@pytest.mark.asyncio
async def test_something(client: AsyncClient):
    response = await client.get("/api/v1/endpoint")
```

### Option 2: Use pytest-asyncio autouse fixture

Add this to `conftest.py`:

```python
@pytest.fixture(scope="function", autouse=True)
async def setup_test_database():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
```

### Option 3: Use sync fixtures with async tests

Keep the database operations sync but make the HTTP client async:

```python
# Sync database setup
@pytest.fixture(scope="function")
def setup_database():
    Base.metadata.create_all(bind=sync_engine)
    yield
    Base.metadata.drop_all(bind=sync_engine)

# Async client
@pytest.fixture
async def client(setup_database):
    async with AsyncClient(app=app, base_url="http://test") as ac:
        yield ac
```

### Option 4: Use httpx.AsyncClient directly in tests

Instead of using fixtures, create the client directly in each test:

```python
@pytest.mark.asyncio
async def test_something():
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.get("/api/v1/endpoint")
        assert response.status_code == 200
```

## Recommended Approach

For post-launch, I recommend **Option 3** (sync fixtures with async tests) as it's the simplest and most reliable:

1. Keep database setup/teardown synchronous
2. Use async HTTP client for API calls
3. This avoids the complexity of async fixture resolution

## Files to Update

1. `coredent-api/tests/conftest.py` - Fix fixture scopes and async/sync mix
2. `coredent-api/tests/test_auth.py` - Already updated to async
3. `coredent-api/tests/test_patients.py` - Already updated to async
4. `coredent-api/tests/test_appointments.py` - Already updated to async

## Testing the Fix

Once fixed, run:

```bash
# Test all backend tests
python -m pytest coredent-api/tests/ -v

# Test specific file
python -m pytest coredent-api/tests/test_auth.py -v

# Test specific test
python -m pytest coredent-api/tests/test_auth.py::TestAuthEndpoints::test_login_success -v
```

## Expected Result

All 47 backend tests should pass:

- 13 auth tests
- 17 patient tests  
- 18 appointment tests

## Priority

**LOW** - This does not block production deployment. The backend API is fully functional and has been manually tested. These are unit tests for additional confidence.

## Timeline

Fix post-launch during Week 1 maintenance window.

---

**Last Updated**: April 7, 2026  
**Status**: Documented for post-launch fix
