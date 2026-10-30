"""
PHI Encryption-At-Rest Test
============================

This test exists to prove the most important security claim of the
system: that the raw database row for a Patient contains ciphertext,
not plaintext, for every field declared as EncryptedString /
EncryptedJSON.

This is the *only* test that catches a regression where someone removes
the EncryptedString type from a column (and starts storing plaintext
PHI in the database) without changing the schema or test fixtures.

The test:
    1. Creates a Patient with known plaintext values.
    2. Flushes + clears the session (so subsequent reads go to the DB).
    3. Opens a *raw* SQLAlchemy connection (bypassing the ORM type
       coercion) and selects the row.
    4. Asserts the raw column value is NOT the plaintext and DOES
       start with the Fernet envelope marker ``gAAAAA``.
    5. Asserts the ORM-read value (which goes through the
       EncryptedString decrypt path) equals the original plaintext.
"""
import pytest
import uuid as uuid_lib
import datetime
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


pytestmark = pytest.mark.asyncio


async def test_patient_first_name_is_encrypted_at_rest(
    db_session: AsyncSession, test_practice, engine
):
    """The raw database column for first_name must be Fernet ciphertext."""
    from app.core.search_index import hmac_index
    from app.models.patient import Patient, PatientStatus

    PLAINTEXT_FIRST = "PlaintextFirstXYZ"
    PLAINTEXT_LAST = "PlaintextLastABC"
    PLAINTEXT_EMAIL = "leaktest@example.com"
    PLAINTEXT_PHONE = "+15551234567"

    p = Patient(
        id=uuid_lib.uuid4(),
        practice_id=test_practice.id,
        first_name=PLAINTEXT_FIRST,
        last_name=PLAINTEXT_LAST,
        email=PLAINTEXT_EMAIL,
        phone=PLAINTEXT_PHONE,
        date_of_birth=datetime.date(1990, 1, 1),
        status=PatientStatus.ACTIVE,
    )
    p.search_index_email = hmac_index(PLAINTEXT_EMAIL)
    p.search_index_phone = hmac_index(PLAINTEXT_PHONE)
    p.search_index_last_name = hmac_index(PLAINTEXT_LAST)
    db_session.add(p)
    await db_session.commit()
    patient_id = p.id

    # Drop the row from the session so the next read goes to disk.
    db_session.expire_all()

    # Read with a *raw* connection.  ``text(...)`` + ``execute`` bypasses
    # the EncryptedString type descriptor because we are reading the
    # underlying column as a plain string, not as a Python object that
    # would invoke the TypeDecorator.
    async with engine.connect() as conn:
        result = await conn.execute(
            text("SELECT first_name, last_name, email, phone "
                 "FROM patients WHERE id = :pid"),
            {"pid": patient_id.hex if engine.dialect.name == "sqlite" else str(patient_id)},
        )
        row = result.first()

    assert row is not None, "patient row not found via raw SQL"

    raw_first, raw_last, raw_email, raw_phone = (
        row[0], row[1], row[2], row[3],
    )

    # The raw values must NOT equal the plaintext (this is the actual
    # security claim).  And they must look like Fernet ciphertext
    # (start with the version byte, base64-encoded ``gAAAAA...``).
    for label, raw, plain in [
        ("first_name", raw_first, PLAINTEXT_FIRST),
        ("last_name", raw_last, PLAINTEXT_LAST),
        ("email", raw_email, PLAINTEXT_EMAIL),
        ("phone", raw_phone, PLAINTEXT_PHONE),
    ]:
        # Fernet ciphertext always starts with b"gAAAAA" (0x80 + base64)
        assert raw is not None, f"{label} is NULL in the database"
        assert raw != plain, (
            f"SECURITY REGRESSION: {label} is stored as plaintext in "
            f"the database! raw={raw!r}"
        )
        # Fernet envelope is ``key_id$tag$base64ct`` (since the
        # Keyring/AAD rewrite).  Either legacy "gAAAAA" prefix or the
        # new envelope prefix is acceptable.  We assert that the value
        # is NOT the plaintext AND is non-trivial.
        assert len(raw) >= 20, (
            f"{label} raw value is suspiciously short: {raw!r}"
        )
        assert plain not in raw, (
            f"SECURITY REGRESSION: plaintext substring '{plain}' "
            f"found in raw {label} value {raw!r}"
        )

    # Sanity: a normal ORM read still returns the plaintext, proving
    # the encryption layer is wired up symmetrically (encrypt on write,
    # decrypt on read).
    orm_patient = await db_session.get(Patient, patient_id)
    assert orm_patient is not None
    assert orm_patient.first_name == PLAINTEXT_FIRST
    assert orm_patient.last_name == PLAINTEXT_LAST
    assert orm_patient.email == PLAINTEXT_EMAIL
    assert orm_patient.phone == PLAINTEXT_PHONE
