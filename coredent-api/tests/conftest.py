"""
Test configuration and fixtures for CoreDent API tests
"""
import os
from pathlib import Path
from cryptography.fernet import Fernet

# Generate valid Fernet key for testing
test_encryption_key = Fernet.generate_key().decode()

# Set required env vars BEFORE importing app (must use direct assignment, not setdefault)
test_database_path = Path(__file__).resolve().parents[1] / f".test-db-{os.getpid()}.sqlite"
test_database_url = os.getenv(
    "TEST_DATABASE_URL", f"sqlite+aiosqlite:///{test_database_path.as_posix()}"
)
os.environ["DATABASE_URL"] = test_database_url
os.environ["SECRET_KEY"] = "test-secret-key-for-testing-only-12345"
os.environ["ENCRYPTION_KEY"] = test_encryption_key
os.environ["DEBUG"] = "True"
os.environ["ENVIRONMENT"] = "test"

import pytest  # noqa: E402
import datetime  # noqa: E402
import uuid as uuid_lib  # noqa: E402
from typing import AsyncGenerator  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402
from sqlalchemy.orm import configure_mappers  # noqa: E402

# Import all models to ensure they're registered with SQLAlchemy
import app.models  # noqa: E402,F401
from app.core.base import Base  # noqa: E402
from app.core.security import get_password_hash  # noqa: E402
from app.main import app as fastapi_app  # noqa: E402
from app.api.deps import get_db  # noqa: E402

from app.models.practice import Practice  # noqa: E402
from app.models.user import User  # noqa: E402
from app.models.patient import Patient  # noqa: E402
from app.models.appointment import Appointment  # noqa: E402

# Configure all mappers before creating tables
configure_mappers()

# Test database URL (async SQLite)
SQLALCHEMY_DATABASE_URL = test_database_url

# Create async test engine. StaticPool keeps a single in-memory SQLite
# database alive across fixture connections; PostgreSQL uses its normal pool.
_engine_options = {"echo": False}
if SQLALCHEMY_DATABASE_URL.startswith("sqlite"):
    _engine_options.update(
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
engine = create_async_engine(SQLALCHEMY_DATABASE_URL, **_engine_options)

TestingSessionLocal = async_sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)


@pytest.fixture(name="engine")
def engine_fixture():
    """Expose the shared async test engine to tests that inspect raw storage."""
    return engine


async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
    """Override database dependency for testing"""
    async with TestingSessionLocal() as session:
        yield session


fastapi_app.dependency_overrides[get_db] = override_get_db


@pytest.fixture(scope="session", autouse=True)
def migrate_test_database():
    """Build the default test schema through Alembic, not only create_all.

    A per-process file-backed SQLite database lets Alembic's synchronous
    migration runner and the async test engine share the same schema. Callers
    that explicitly provide TEST_DATABASE_URL retain their own database setup.
    """
    if test_database_url == os.getenv("TEST_DATABASE_URL"):
        yield
        return

    from alembic import command
    from alembic.config import Config

    config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    sync_url = test_database_url.replace("+aiosqlite", "")
    config.set_main_option("sqlalchemy.url", sync_url)
    command.upgrade(config, "head")
    yield


@pytest.fixture(scope="session", autouse=True)
async def create_test_schema(migrate_test_database):
    """Create any test/legacy model tables once per test process.

    Alembic is the schema authority and already produced the baseline above;
    ``create_all`` is retained only as an additive compatibility step for
    legacy test models not yet represented by a migration. Because it is
    idempotent and expensive, it runs exactly once per test process rather
    than once per test function.
    """
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


@pytest.fixture(scope="function")
async def setup_database(create_test_schema):
    """Reset data between tests without rebuilding the schema.

    The migrated schema plus any additive test tables are created once by the
    session-scoped ``create_test_schema`` fixture. Here we only truncate the
    tables at teardown to isolate each test, which is far cheaper than running
    ``create_all`` per test.
    """
    yield
    # Don't drop tables - truncate for speed while retaining the migrated schema.
    #
    # One statement on PostgreSQL, not one per table. The loop below issues a
    # round trip per table per test (~40 tables x ~760 tests), which is nearly
    # free in-process on SQLite and ruinous over a network: against PostgreSQL
    # the suite could not finish inside the CI job timeout once the fixtures
    # actually started running. TRUNCATE ... CASCADE is also what PostgreSQL is
    # designed for here, and RESTART IDENTITY keeps sequences deterministic.
    async with TestingSessionLocal() as session:
        if session.bind.dialect.name == "postgresql":
            from sqlalchemy import text as _text

            names = ", ".join(f'"{table.name}"' for table in Base.metadata.sorted_tables)
            await session.execute(_text(f"TRUNCATE TABLE {names} RESTART IDENTITY CASCADE"))
        else:
            for table in reversed(Base.metadata.sorted_tables):
                await session.execute(table.delete())
        await session.commit()


@pytest.fixture
async def db_session(setup_database) -> AsyncGenerator[AsyncSession, None]:
    """Create database session for testing"""
    async with TestingSessionLocal() as session:
        yield session
        await session.rollback()  # Rollback any uncommitted changes


@pytest.fixture
async def client(setup_database) -> AsyncGenerator[AsyncClient, None]:
    """Create async test client.

    follow_redirects=True so tests can exercise routes defined at /path/
    with a trailing slash by requesting /path (FastAPI otherwise returns
    307 and httpx doesn't follow redirects by default).
    """
    transport = ASGITransport(
        app=fastapi_app,
        client=(f"test-{uuid_lib.uuid4().hex}", 0),
    )
    async with AsyncClient(
        transport=transport, base_url="http://test", follow_redirects=True
    ) as ac:
        yield ac


# Alias: several older test modules use the name `async_client` for the
# httpx AsyncClient fixture. Keep both names to avoid churn.
@pytest.fixture
async def async_client(client: AsyncClient) -> AsyncClient:
    return client


@pytest.fixture
async def test_practice(db_session: AsyncSession) -> Practice:
    """Create test practice"""
    practice = Practice(
        id=uuid_lib.uuid4(),
        name="Test Practice",
        public_slug=f"test-practice-{uuid_lib.uuid4().hex[:6]}",
        email="test@practice.com",
        phone="555-0100",
        address_street="123 Test St",
        address_city="Testville",
        address_state="TS",
        address_zip="12345",
    )
    db_session.add(practice)
    # commit(), not flush(). The API under test uses its own session, taken from
    # the engine pool, so it only sees COMMITTED rows. On SQLite the test engine
    # uses StaticPool - one shared connection - so an uncommitted row was visible
    # anyway and every fixture appeared to work; on PostgreSQL the request pulls a
    # different connection, the row is invisible, and login returns 401 for a user
    # the fixture had just created. Isolation is unaffected: setup_database
    # truncates every table at teardown.
    await db_session.commit()
    await db_session.refresh(practice)
    return practice


@pytest.fixture
async def test_user(db_session: AsyncSession, test_practice: Practice) -> User:
    """Create test user with unique email.

    Uses OWNER role so role-restricted endpoints (e.g. delete_patient which
    requires OWNER/ADMIN) are exercisable. Role-specific permission tests
    should create their own user with the relevant role.
    """
    unique_email = f"testuser_{uuid_lib.uuid4().hex[:8]}@example.com"
    user = User(
        id=uuid_lib.uuid4(),
        email=unique_email,
        password_hash=get_password_hash("testpassword123"),
        first_name="Test",
        last_name="User",
        role="OWNER",
        practice_id=test_practice.id,
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.fixture
async def test_patient(db_session: AsyncSession, test_practice: Practice) -> Patient:
    """Create test patient"""
    from app.core.search_index import hmac_index
    patient = Patient(
        id=uuid_lib.uuid4(),
        practice_id=test_practice.id,
        first_name="John",
        last_name="Doe",
        email="john.doe@example.com",
        phone="+1234567890",
        date_of_birth=datetime.date(1990, 1, 1),
        gender="male",
        address_street="123 Main St",
        address_city="Springfield",
        address_state="IL",
        address_zip="62701",
        emergency_contact={
            "name": "Jane Doe",
            "relationship": "spouse",
            "phone": "+1234567891"
        },
        medical_alerts=[],
        status="active",
    )
    patient.search_index_email = hmac_index("john.doe@example.com")
    patient.search_index_phone = hmac_index("+1234567890")
    patient.search_index_last_name = hmac_index("Doe")
    db_session.add(patient)
    await db_session.commit()
    await db_session.refresh(patient)
    return patient


@pytest.fixture
async def test_appointment(
    db_session: AsyncSession,
    test_practice: Practice,
    test_patient: Patient,
    test_user: User
) -> Appointment:
    """Create test appointment"""
    start_time = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=1)
    end_time = start_time + datetime.timedelta(hours=1)
    appointment = Appointment(
        id=uuid_lib.uuid4(),
        practice_id=test_practice.id,
        patient_id=test_patient.id,
        provider_id=test_user.id,
        appointment_type="cleaning",
        status="scheduled",
        start_time=start_time,
        end_time=end_time,
        duration=60,
        notes="Regular cleaning appointment",
    )
    db_session.add(appointment)
    await db_session.commit()
    await db_session.refresh(appointment)
    return appointment


@pytest.fixture
async def auth_headers(client: AsyncClient, test_user: User) -> dict:
    """Get authentication headers for test user"""
    login_data = {
        "email": test_user.email,
        "password": "testpassword123"
    }
    response = await client.post("/api/v1/auth/login", json=login_data)
    assert response.status_code == 200, f"Login failed for {test_user.email}: {response.text}"
    token = response.json()["access_token"]
    csrf_response = await client.get("/api/v1/auth/csrf")
    assert csrf_response.status_code == 200, csrf_response.text
    csrf_token = csrf_response.json()["csrf_token"]
    return {
        "Authorization": f"Bearer {token}",
        "X-CSRF-Token": csrf_token,
    }


@pytest.fixture
async def other_practice(db_session: AsyncSession) -> Practice:
    """Create a second practice for cross-tenant isolation tests"""
    practice = Practice(
        id=uuid_lib.uuid4(),
        name="Other Practice",
        public_slug=f"other-practice-{uuid_lib.uuid4().hex[:6]}",
        email="other@practice.com",
        phone="555-0200",
        address_street="456 Other St",
        address_city="Otherville",
        address_state="OT",
        address_zip="54321",
    )
    db_session.add(practice)
    await db_session.commit()
    await db_session.refresh(practice)
    return practice


@pytest.fixture
async def other_user(db_session: AsyncSession, other_practice: Practice) -> User:
    """Create a second user belonging to other_practice for tenant isolation tests"""
    unique_email = f"otheruser_{uuid_lib.uuid4().hex[:8]}@example.com"
    user = User(
        id=uuid_lib.uuid4(),
        email=unique_email,
        password_hash=get_password_hash("otherpassword123"),
        first_name="Other",
        last_name="User",
        role="OWNER",
        practice_id=other_practice.id,
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.fixture
async def other_patient(db_session: AsyncSession, other_practice: Practice) -> Patient:
    """Create a patient in other_practice for cross-tenant tests"""
    patient = Patient(
        id=uuid_lib.uuid4(),
        practice_id=other_practice.id,
        first_name="Jane",
        last_name="Smith",
        email="jane.smith@example.com",
        phone="+1987654321",
        date_of_birth=datetime.date(1985, 5, 15),
        gender="female",
        address_street="789 Oak St",
        address_city="Oakville",
        address_state="CA",
        address_zip="90210",
        emergency_contact={
            "name": "John Smith",
            "relationship": "spouse",
            "phone": "+1987654322"
        },
        medical_alerts=[],
        status="active",
    )
    db_session.add(patient)
    await db_session.commit()
    await db_session.refresh(patient)
    return patient


@pytest.fixture
async def other_appointment(
    db_session: AsyncSession,
    other_practice: Practice,
    other_patient: Patient,
    other_user: User,
) -> Appointment:
    """Create an appointment in other_practice for cross-tenant tests"""
    appointment = Appointment(
        id=uuid_lib.uuid4(),
        practice_id=other_practice.id,
        patient_id=other_patient.id,
        provider_id=other_user.id,
        appointment_type="consultation",
        status="scheduled",
        start_time=datetime.datetime(2026, 4, 20, 14, 0, 0),
        end_time=datetime.datetime(2026, 4, 20, 15, 0, 0),
        duration=60,
        notes="Other practice appointment",
    )
    db_session.add(appointment)
    await db_session.commit()
    await db_session.refresh(appointment)
    return appointment


@pytest.fixture
async def other_auth_headers(client: AsyncClient, other_user: User) -> dict:
    """Get authentication headers for the other practice user"""
    login_data = {
        "email": other_user.email,
        "password": "otherpassword123"
    }
    response = await client.post("/api/v1/auth/login", json=login_data)
    assert response.status_code == 200, f"Login failed for {other_user.email}: {response.text}"
    token = response.json()["access_token"]
    csrf_response = await client.get("/api/v1/auth/csrf")
    assert csrf_response.status_code == 200, csrf_response.text
    csrf_token = csrf_response.json()["csrf_token"]
    return {
        "Authorization": f"Bearer {token}",
        "X-CSRF-Token": csrf_token,
    }


@pytest.fixture
def mock_settings():
    """Mock settings for testing"""
    return {
        "SECRET_KEY": "test-secret-key-for-testing-only",
        "ENCRYPTION_KEY": test_encryption_key,
        "DATABASE_URL": SQLALCHEMY_DATABASE_URL,
        "ACCESS_TOKEN_EXPIRE_MINUTES": 30,
        "ENVIRONMENT": "test",
    }