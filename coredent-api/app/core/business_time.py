"""Practice-timezone business-time and bounded-range helpers.

A business day belongs to the practice's configured IANA timezone, never the
application host or requester's browser. Timestamps remain UTC instants in the
database; date-only filters are converted to UTC half-open bounds before SQL
so they are DST-correct and index-friendly.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone, tzinfo
from typing import Any, Optional
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

DEFAULT_TZ_NAME = "UTC"
DEFAULT_INTERACTIVE_RANGE_DAYS = 90
MAX_INTERACTIVE_RANGE_DAYS = 366
MAX_AVAILABILITY_RANGE_DAYS = 31


class DateRangeError(ValueError):
    """A caller supplied an invalid or operationally unsafe date range."""


@dataclass(frozen=True)
class BusinessDateRange:
    """Inclusive local dates plus their UTC half-open query bounds."""

    start_date: date
    end_date: date
    start_utc: datetime
    end_utc: datetime


@dataclass(frozen=True)
class InstantRange:
    """UTC half-open bounds for legacy timestamp-based request contracts."""

    start_utc: datetime
    end_utc: datetime


def resolve_timezone(tz_name: Optional[str]) -> tzinfo:
    """Build a tzinfo from an IANA name, falling back safely to UTC."""
    if not tz_name:
        return timezone.utc
    try:
        return ZoneInfo(tz_name)
    except (TypeError, ZoneInfoNotFoundError, ValueError, OSError):
        logger.warning("Invalid practice timezone %r; falling back to UTC", tz_name)
        return timezone.utc


def practice_timezone_of(practice: Any) -> tzinfo:
    """Resolve the timezone of an already-loaded practice object."""
    return resolve_timezone(getattr(practice, "timezone", None))


async def get_practice_timezone(db: AsyncSession, practice_id: Any) -> tzinfo:
    """Resolve a practice timezone with one scalar query."""
    if practice_id is None:
        return timezone.utc
    from app.models.practice import Practice

    result = await db.execute(
        select(Practice.timezone).where(Practice.id == practice_id)
    )
    return resolve_timezone(result.scalar_one_or_none())


async def get_practice_timezone_name(db: AsyncSession, practice_id: Any) -> str:
    """Resolve a validated IANA name for SQL-side local-day bucketing."""
    if practice_id is None:
        return DEFAULT_TZ_NAME
    from app.models.practice import Practice

    result = await db.execute(
        select(Practice.timezone).where(Practice.id == practice_id)
    )
    tz_name = result.scalar_one_or_none()
    resolved = resolve_timezone(tz_name)
    return tz_name if resolved is not timezone.utc or tz_name == DEFAULT_TZ_NAME else DEFAULT_TZ_NAME


def ensure_utc(moment: Optional[datetime]) -> Optional[datetime]:
    """Normalize a database/request datetime to an aware UTC instant.

    Legacy SQLite fixtures can deserialize timestamp columns without tzinfo;
    they are intentionally interpreted as UTC rather than server-local time.
    """
    if moment is None:
        return None
    if moment.tzinfo is None:
        return moment.replace(tzinfo=timezone.utc)
    return moment.astimezone(timezone.utc)


def business_date(tz: tzinfo, moment: Optional[datetime] = None) -> date:
    """Calendar date of an instant as observed in a practice timezone."""
    instant = ensure_utc(moment) or datetime.now(timezone.utc)
    return instant.astimezone(tz).date()


def business_now(tz: tzinfo) -> datetime:
    """Current timezone-aware wall-clock time for a practice."""
    return datetime.now(timezone.utc).astimezone(tz)


def day_bounds_utc(tz: tzinfo, day: date) -> tuple[datetime, datetime]:
    """UTC half-open range ``[start, end)`` covering one local calendar day."""
    start_local = datetime.combine(day, time.min, tzinfo=tz)
    end_local = datetime.combine(day + timedelta(days=1), time.min, tzinfo=tz)
    return start_local.astimezone(timezone.utc), end_local.astimezone(timezone.utc)


def range_bounds_utc(
    tz: tzinfo, from_date: date, to_date: date
) -> tuple[datetime, datetime]:
    """UTC half-open range covering local dates ``from_date`` through ``to_date``."""
    if to_date < from_date:
        raise DateRangeError("end date must not be before start date")
    start_local = datetime.combine(from_date, time.min, tzinfo=tz)
    end_local = datetime.combine(to_date + timedelta(days=1), time.min, tzinfo=tz)
    return start_local.astimezone(timezone.utc), end_local.astimezone(timezone.utc)


def resolve_date_range(
    tz: tzinfo,
    start_date: Optional[date],
    end_date: Optional[date],
    *,
    default_days: int = DEFAULT_INTERACTIVE_RANGE_DAYS,
    max_days: int = MAX_INTERACTIVE_RANGE_DAYS,
    moment: Optional[datetime] = None,
) -> BusinessDateRange:
    """Resolve optional local dates into a safe inclusive calendar window.

    Missing bounds derive a bounded companion instead of creating an unbounded
    historical scan. Explicit reversed or oversized ranges fail deterministically.
    """
    if default_days < 1 or max_days < 1 or default_days > max_days:
        raise ValueError("range configuration must satisfy 1 <= default_days <= max_days")

    today = business_date(tz, moment)
    if start_date is None and end_date is None:
        end_date = today
        start_date = end_date - timedelta(days=default_days - 1)
    elif start_date is None:
        start_date = end_date - timedelta(days=default_days - 1)
    elif end_date is None:
        end_date = start_date + timedelta(days=default_days - 1)

    if end_date < start_date:
        raise DateRangeError("end date must not be before start date")
    span_days = (end_date - start_date).days + 1
    if span_days > max_days:
        raise DateRangeError(f"date range may not exceed {max_days} days")

    start_utc, end_utc = range_bounds_utc(tz, start_date, end_date)
    return BusinessDateRange(start_date, end_date, start_utc, end_utc)


def resolve_instant_range(
    tz: tzinfo,
    start: Optional[datetime],
    end: Optional[datetime],
    *,
    default_days: int = DEFAULT_INTERACTIVE_RANGE_DAYS,
    max_days: int = MAX_INTERACTIVE_RANGE_DAYS,
    moment: Optional[datetime] = None,
) -> InstantRange:
    """Resolve legacy datetime filters to bounded UTC half-open bounds.

    A supplied datetime retains instant semantics. Omitted bounds derive a
    practice-local date range, avoiding a server-timezone-dependent default.
    """
    if default_days < 1 or max_days < 1 or default_days > max_days:
        raise ValueError("range configuration must satisfy 1 <= default_days <= max_days")

    start_utc = ensure_utc(start)
    end_utc = ensure_utc(end)
    if start_utc is None and end_utc is None:
        default_range = resolve_date_range(
            tz,
            None,
            None,
            default_days=default_days,
            max_days=max_days,
            moment=moment,
        )
        return InstantRange(default_range.start_utc, default_range.end_utc)

    default_interval = timedelta(days=default_days)
    if start_utc is None:
        start_utc = end_utc - default_interval
    elif end_utc is None:
        end_utc = start_utc + default_interval

    if end_utc <= start_utc:
        raise DateRangeError("end time must be after start time")
    if end_utc - start_utc > timedelta(days=max_days):
        raise DateRangeError(f"time range may not exceed {max_days} days")
    return InstantRange(start_utc, end_utc)


def local_datetime(tz: tzinfo, day: date, wall_time: time, *, fold: int = 0) -> datetime:
    """Create a valid local datetime for public wall-clock booking input.

    Nonexistent spring-forward times are rejected. Ambiguous fall-back times
    intentionally select the first occurrence (``fold=0``) until the public
    contract adds an explicit fold/offset selector.
    """
    candidate = datetime.combine(day, wall_time, tzinfo=tz).replace(fold=fold)
    round_trip = candidate.astimezone(timezone.utc).astimezone(tz)
    if round_trip.replace(tzinfo=None) != candidate.replace(tzinfo=None):
        raise DateRangeError("requested local time does not exist in this timezone")
    return candidate


def day_expr(column, tz_name: Optional[str]):
    """SQL expression bucketing a timestamp into its practice-local date.

    Use this only for ``GROUP BY``; use UTC ranges above for predicates so
    database indexes remain usable.
    """
    from app.core.database import engine_url

    zone = tz_name or DEFAULT_TZ_NAME
    if engine_url.startswith("postgresql"):
        return func.date(func.timezone(zone, column))
    return func.date(column)


def iter_days(from_date: date, to_date: date):
    """Yield local dates inclusively after validating the requested order."""
    if to_date < from_date:
        raise DateRangeError("end date must not be before start date")
    current = from_date
    while current <= to_date:
        yield current
        current += timedelta(days=1)
