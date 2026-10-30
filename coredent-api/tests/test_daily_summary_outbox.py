"""Daily-summary outbox durability tests (B7-9)."""

import pytest
from sqlalchemy.exc import IntegrityError

from app.models.daily_summary import DailySummaryOutbox, DailySummaryStatus
from datetime import date

pytestmark = pytest.mark.asyncio


async def test_outbox_row_unique_per_practice_date_user(db_session, test_practice, test_user):
    """One summary per practice/local-date/recipient: the unique constraint is
    the concurrency guard that makes concurrent scheduler runs converge."""
    row = DailySummaryOutbox(
        practice_id=test_practice.id,
        user_id=test_user.id,
        summary_date=date(2026, 8, 25),
        recipient_email=test_user.email,
        status=DailySummaryStatus.PENDING,
    )
    db_session.add(row)
    await db_session.commit()

    duplicate = DailySummaryOutbox(
        practice_id=test_practice.id,
        user_id=test_user.id,
        summary_date=date(2026, 8, 25),
        recipient_email=test_user.email,
        status=DailySummaryStatus.PENDING,
    )
    db_session.add(duplicate)
    with pytest.raises(IntegrityError):
        await db_session.commit()
    await db_session.rollback()


async def test_same_recipient_different_days_allowed(db_session, test_practice, test_user):
    """The constraint is per local summary DATE, not globally per recipient."""
    for day in (date(2026, 8, 24), date(2026, 8, 25)):
        db_session.add(
            DailySummaryOutbox(
                practice_id=test_practice.id,
                user_id=test_user.id,
                summary_date=day,
                recipient_email=test_user.email,
                status=DailySummaryStatus.SENT,
            )
        )
    await db_session.commit()
