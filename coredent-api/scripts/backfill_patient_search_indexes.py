"""Backfill deterministic HMAC indexes for encrypted patient fields.

Run only after applying Alembic revision ``7f3c8a1d2e4b`` and with the same
encryption/search-index keys used by the application. The command never logs
patient values. It fails closed if any encrypted field cannot be decrypted.

Examples:
    python scripts/backfill_patient_search_indexes.py
    python scripts/backfill_patient_search_indexes.py --verify
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

from sqlalchemy import and_, func, or_, select


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.core.database import AsyncSessionLocal, engine  # noqa: E402
from app.core.search_index import update_patient_search_indexes  # noqa: E402
from app.models.patient import Patient  # noqa: E402


DECRYPTION_FAILURE = "[DECRYPTION_FAILED]"


def _missing_index_predicate():
    return or_(
        and_(
            Patient.email.is_not(None),
            Patient.email != "",
            Patient.search_index_email.is_(None),
        ),
        and_(
            Patient.phone.is_not(None),
            Patient.phone != "",
            Patient.search_index_phone.is_(None),
        ),
        and_(
            Patient.last_name.is_not(None),
            Patient.last_name != "",
            Patient.search_index_last_name.is_(None),
        ),
    )


async def _remaining_count(session) -> int:
    result = await session.execute(
        select(func.count(Patient.id)).where(_missing_index_predicate())
    )
    return int(result.scalar_one())


async def verify() -> int:
    async with AsyncSessionLocal() as session:
        remaining = await _remaining_count(session)
    if remaining:
        print(f"FAILED: {remaining} patient rows still require search-index backfill.")
        return 1
    print("VERIFIED: no eligible patient rows are missing search indexes.")
    return 0


async def backfill(batch_size: int) -> int:
    processed = 0
    async with AsyncSessionLocal() as session:
        while True:
            result = await session.execute(
                select(Patient)
                .where(_missing_index_predicate())
                .order_by(Patient.id)
                .limit(batch_size)
                .with_for_update(skip_locked=True)
            )
            patients = list(result.scalars())
            if not patients:
                break

            for patient in patients:
                values = (patient.email, patient.phone, patient.last_name)
                if DECRYPTION_FAILURE in values:
                    await session.rollback()
                    raise RuntimeError(
                        "Patient PHI decryption failed; no indexes were written for this batch. "
                        "Verify ENCRYPTION_KEYS before retrying."
                    )
                update_patient_search_indexes(
                    patient,
                    "email",
                    "phone",
                    "last_name",
                )

            await session.commit()
            processed += len(patients)
            print(f"Backfilled {processed} patient rows.")

        remaining = await _remaining_count(session)

    if remaining:
        print(
            f"FAILED: {remaining} rows remain (possibly locked by another process). "
            "Retry before enabling patient portal access."
        )
        return 1
    print(f"COMPLETE: backfilled {processed} patient rows; verification passed.")
    return 0


async def _main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify", action="store_true", help="Check only; do not write")
    parser.add_argument("--batch-size", type=int, default=250)
    args = parser.parse_args()
    if args.batch_size < 1 or args.batch_size > 5000:
        parser.error("--batch-size must be between 1 and 5000")
    return await (verify() if args.verify else backfill(args.batch_size))


async def _run() -> int:
    try:
        return await _main()
    finally:
        await engine.dispose()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_run()))
