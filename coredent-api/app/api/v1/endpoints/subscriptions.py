"""
Subscription Endpoints (Refactored)
Uses service layer for business logic
"""

from fastapi import APIRouter, Depends, HTTPException, status, Request, Query, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc
from typing import Optional, List, Literal
from datetime import datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP
from uuid import UUID
import logging

from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from app.core.database import get_db
from app.core.config_simple import settings
from app.api.deps import get_current_user, require_role, verify_csrf
from app.models.user import User, UserRole
from app.models.practice import Practice
from app.core.audit import log_audit_event
from app.models.subscription import (
    SubscriptionPlan,
    Subscription,
    SubscriptionStatus,
)
from app.schemas.subscription import (
    SubscriptionPlanCreate,
    SubscriptionPlanUpdate,
    SubscriptionPlanResponse,
    SubscriptionPlanList,
    SubscriptionCreate,
    SubscriptionResponse,
    SubscriptionList,
    SubscriptionPause,
    SubscriptionCancellation,
    SubscriptionChangePlan,
    UsageRecordCreate,
    UsageRecordResponse,
    UsageResponse,
    DunningEventList,
    SubscriptionStats,
    TrialResponse,
)
from app.schemas.common import APIResponse

# Import services
from app.services.subscription_service import SubscriptionService
from app.services.subscription_billing import SubscriptionBillingService
from app.services.subscription_webhooks import (
    SubscriptionWebhookHandler,
    WebhookDeduplicationUnavailable,
)

logger = logging.getLogger(__name__)
router = APIRouter()

# Our SubscriptionInterval values -> Stripe ``recurring`` interval strings.
# Module-level so the None-mapping regression guard in
# tests/test_phase3_fix_regressions.py exercises the LIVE mapping that
# actually builds Stripe prices. An unsupported value must fall back to a
# valid interval (``.get(..., default)``), never map to None.
# Typed as StripeRecurringInterval because the Stripe SDK's ``recurring``
# payload requires one of exactly these four literals — a plain str would
# not be checked against the allowed set.
StripeRecurringInterval = Literal["week", "month", "year"]

STRIPE_INTERVAL_MAP: dict[str, StripeRecurringInterval] = {
    "weekly": "week",
    "monthly": "month",
    "quarterly": "month",
    "semi_annual": "month",
    "annual": "year",
}

# Stripe ``recurring.interval_count`` for each of our interval values.
STRIPE_INTERVAL_COUNT: dict[str, int] = {
    "weekly": 1,
    "monthly": 1,
    "quarterly": 3,
    "semi_annual": 6,
    "annual": 1,
}

# ======================= Subscription Plan Endpoints =======================

@router.get("/plans", response_model=SubscriptionPlanList)
async def list_subscription_plans(
    active_only: bool = Query(True),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SubscriptionPlanList:
    """List all available subscription plans"""
    query = select(SubscriptionPlan).where(SubscriptionPlan.practice_id.is_(None))

    if active_only:
        query = query.where(SubscriptionPlan.is_active.is_(True))

    query = query.order_by(SubscriptionPlan.sort_order, SubscriptionPlan.amount)
    result = await db.execute(query)
    plans = result.scalars().all()

    return SubscriptionPlanList(plans=plans, total=len(plans))


@router.post("/plans", response_model=SubscriptionPlanResponse)
async def create_subscription_plan(
    plan_data: SubscriptionPlanCreate,
    current_user: User = Depends(require_role(UserRole.OWNER, UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
    _csrf: bool = Depends(verify_csrf),
) -> SubscriptionPlanResponse:
    """Create a new subscription plan (Owner/Admin only)"""
    # Create Stripe Price if configured
    if settings.STRIPE_API_KEY and not plan_data.stripe_price_id:
        try:
            import asyncio
            import stripe as stripe_lib
            stripe_lib.api_key = settings.STRIPE_API_KEY

            # Create product (sync SDK — offload to a thread)
            product = await asyncio.to_thread(
                stripe_lib.Product.create,
                name=plan_data.name,
                description=plan_data.description,
                metadata={"coredent_plan": "true"},
            )

            # Create price. Uses the module-level interval maps (see
            # STRIPE_INTERVAL_MAP above) so unsupported values fall back to
            # a valid interval rather than mapping to None.
            from app.services.payment_processing import _to_cents
            price = await asyncio.to_thread(
                stripe_lib.Price.create,
                product=product.id,
                unit_amount=_to_cents(plan_data.amount),
                currency=plan_data.currency.lower(),
                recurring={
                    "interval": STRIPE_INTERVAL_MAP.get(plan_data.interval, "month"),
                    "interval_count": STRIPE_INTERVAL_COUNT.get(plan_data.interval, 1),
                },
            )

            plan_data.stripe_price_id = price.id
            plan_data.stripe_product_id = product.id

        except (ValueError, TypeError) as e:
            logger.error(f"Stripe error: {e}")
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Stripe error: {str(e)}")

    plan = SubscriptionPlan(
        **plan_data.model_dump(),
        practice_id=current_user.practice_id,
    )
    db.add(plan)
    await db.commit()
    await db.refresh(plan)

    return plan


@router.put("/plans/{plan_id}", response_model=SubscriptionPlanResponse)
async def update_subscription_plan(
    plan_id: UUID,
    plan_data: SubscriptionPlanUpdate,
    current_user: User = Depends(require_role(UserRole.OWNER, UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
    _csrf: bool = Depends(verify_csrf),
) -> SubscriptionPlanResponse:
    """Update an existing subscription plan

    SECURITY: only plans owned by the caller's practice are editable.
    Platform-global plans (practice_id IS NULL) are shared billing
    configuration for every tenant; letting one practice's admin mutate
    them was a cross-tenant write. Global plans are read-only here by
    design (no superuser surface exists yet).
    """
    result = await db.execute(
        select(SubscriptionPlan).where(
            SubscriptionPlan.id == plan_id,
            SubscriptionPlan.practice_id == current_user.practice_id,
        )
    )
    plan = result.scalar_one_or_none()

    if not plan:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plan not found")

    update_data = plan_data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(plan, key, value)

    await db.commit()
    await db.refresh(plan)
    return plan


@router.get("/plans/{plan_id}", response_model=SubscriptionPlanResponse)
async def get_subscription_plan(
    plan_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SubscriptionPlanResponse:
    """Get a specific subscription plan"""
    result = await db.execute(
        select(SubscriptionPlan).where(
            SubscriptionPlan.id == plan_id,
            (SubscriptionPlan.practice_id.is_(None) | (SubscriptionPlan.practice_id == current_user.practice_id)),
        )
    )
    plan = result.scalar_one_or_none()

    if not plan:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plan not found")

    return plan


# ======================= Subscription Management Endpoints =======================

@router.get("", response_model=SubscriptionList)
async def list_subscriptions(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    status_filter: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SubscriptionList:
    """List all subscriptions for the practice"""
    query = select(Subscription).where(Subscription.practice_id == current_user.practice_id)

    if status_filter:
        try:
            status_enum = SubscriptionStatus(status_filter)
            query = query.where(Subscription.status == status_enum)
        except ValueError:
            pass

    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    offset = (page - 1) * limit
    query = query.order_by(desc(Subscription.created_at)).offset(offset).limit(limit)
    result = await db.execute(query)
    subscriptions = result.scalars().all()

    return SubscriptionList(subscriptions=subscriptions, total=total, page=page, limit=limit)


@router.post("", response_model=SubscriptionResponse)
async def create_subscription(
    request: Request,
    sub_data: SubscriptionCreate,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(require_role(UserRole.OWNER, UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
    _csrf: bool = Depends(verify_csrf),
) -> SubscriptionResponse:
    """Create a subscription under a practice-scoped transaction lock."""
    # The active-subscription check and local insert must be serialized. The
    # external processor call intentionally occurs while this row lock is
    # held, so a concurrent request cannot pass the check before the winner
    # commits its local subscription.
    practice_result = await db.execute(
        select(Practice)
        .where(Practice.id == current_user.practice_id)
        .with_for_update()
    )
    if practice_result.scalar_one_or_none() is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Practice not found")

    # Get a global plan or a plan owned by the current practice.
    result = await db.execute(
        select(SubscriptionPlan).where(
            SubscriptionPlan.id == sub_data.plan_id,
            (SubscriptionPlan.practice_id.is_(None) | (SubscriptionPlan.practice_id == current_user.practice_id)),
        )
    )
    plan = result.scalar_one_or_none()

    if not plan or not plan.is_active:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plan not found or inactive")

    if sub_data.patient_id:
        from app.models.patient import Patient
        patient_result = await db.execute(
            select(Patient).where(
                Patient.id == sub_data.patient_id,
                Patient.practice_id == current_user.practice_id,
            )
        )
        if not patient_result.scalar_one_or_none():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient not found")

    if sub_data.payment_card_id:
        from app.models.payment import PaymentCard
        card_result = await db.execute(
            select(PaymentCard).where(
                PaymentCard.id == sub_data.payment_card_id,
                PaymentCard.practice_id == current_user.practice_id,
                PaymentCard.patient_id == sub_data.patient_id if sub_data.patient_id else True,
                PaymentCard.is_active.is_(True),
            )
        )
        if not card_result.scalar_one_or_none():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payment card not found")

    # Check for existing active subscription
    existing = await db.execute(
        select(Subscription).where(
            Subscription.practice_id == current_user.practice_id,
            Subscription.status.in_([SubscriptionStatus.ACTIVE, SubscriptionStatus.TRIALING, SubscriptionStatus.PAST_DUE]),
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="An active subscription already exists"
        )

    # Allocate the tenant-owned local identity before contacting Stripe. The
    # UUID becomes the webhook ownership root; metadata alone can never create
    # or attach a local subscription.
    now = datetime.now(timezone.utc)
    trial_days = sub_data.trial_period_days or plan.trial_period_days
    trial_end = now + timedelta(days=trial_days) if trial_days > 0 else None
    period_start, period_end = SubscriptionService.calculate_period_start_end(
        plan.interval, trial_end or now
    )
    subscription = Subscription(
        practice_id=current_user.practice_id,
        patient_id=sub_data.patient_id,
        plan_id=sub_data.plan_id,
        payment_card_id=sub_data.payment_card_id,
        status=SubscriptionStatus.INCOMPLETE,
        interval=plan.interval,
        current_period_start=period_start,
        current_period_end=period_end,
        next_billing_date=trial_end or period_end,
        trial_start=now if trial_end else None,
        trial_end=trial_end,
    )
    db.add(subscription)
    await db.flush()

    try:
        stripe_sub_id, stripe_cust_id = await SubscriptionService.create_stripe_subscription(
            db,
            plan,
            current_user.email,
            current_user.full_name,
            current_user.practice_id,
            current_user.id,
            subscription.id,
            sub_data.payment_card_id,
            sub_data.trial_period_days or plan.trial_period_days,
            sub_data.idempotency_key or request.headers.get("Idempotency-Key"),
        )
    except (ValueError, TypeError, SQLAlchemyError) as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    if not stripe_sub_id:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Billing provider is not configured; no subscription was created.",
        )

    # Activate the pre-authorized local row only after Stripe returns a
    # processor identity. Webhooks can now update this UUID but cannot create it.
    subscription.status = (
        SubscriptionStatus.TRIALING if trial_days > 0 else SubscriptionStatus.ACTIVE
    )
    subscription.stripe_subscription_id = stripe_sub_id
    subscription.stripe_customer_id = stripe_cust_id

    await log_audit_event(
        db, current_user, "create_subscription", "subscription", subscription.id, request,
        {"plan_id": str(sub_data.plan_id), "trial_days": trial_days}
    )

    try:
        await db.commit()
    except IntegrityError:
        # A webhook or a retried request may have inserted the same Stripe
        # subscription between our check and commit. The unique identity index
        # makes the race safe; return the committed winner instead of 500.
        await db.rollback()
        winner_result = await db.execute(
            select(Subscription).where(
                Subscription.stripe_subscription_id == stripe_sub_id,
                Subscription.practice_id == current_user.practice_id,
            )
        )
        winner = winner_result.scalar_one_or_none()
        if winner is None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Subscription creation conflicted; please retry.",
            )
        return winner
    await db.refresh(subscription)

    # Send trial email in background
    if trial_end:
        background_tasks.add_task(
            SubscriptionBillingService.send_trial_expiring_email,
            current_user.email,
            str(subscription.id),
            trial_end
        )

    return subscription


@router.get("/stats", response_model=SubscriptionStats)
async def get_subscription_stats(
    current_user: User = Depends(require_role(UserRole.OWNER, UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> SubscriptionStats:
    """Get subscription statistics for dashboard"""
    stats = await SubscriptionBillingService.get_subscription_stats(db, current_user.practice_id)
    return SubscriptionStats(**stats)


@router.get("/{subscription_id}", response_model=SubscriptionResponse)
async def get_subscription(
    subscription_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SubscriptionResponse:
    """Get a specific subscription"""
    sub = await SubscriptionService.get_subscription_with_plan(db, subscription_id, current_user.practice_id)
    if not sub:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Subscription not found")
    return sub


@router.get("/{subscription_id}/trial", response_model=TrialResponse)
async def get_trial_info(
    subscription_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TrialResponse:
    """Get trial information for a subscription"""
    sub = await SubscriptionService.get_subscription_with_plan(db, subscription_id, current_user.practice_id)
    if not sub:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Subscription not found")
    if not sub.trial_end:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No trial on this subscription")

    now = datetime.now(timezone.utc)
    days_used = int((now - sub.trial_start).total_seconds() / 86400) if sub.trial_start else 0
    days_remaining = int((sub.trial_end - now).total_seconds() / 86400) if sub.trial_end else 0

    return TrialResponse(
        subscription_id=sub.id,
        plan_name=sub.plan.name if sub.plan else "",
        trial_start=sub.trial_start,
        trial_end=sub.trial_end,
        days_remaining=max(0, days_remaining),
        days_used=days_used,
        used=sub.trial_used,
    )


@router.post("/{subscription_id}/cancel", response_model=SubscriptionResponse)
async def cancel_subscription(
    subscription_id: UUID,
    cancel_data: SubscriptionCancellation,
    request: Request,
    current_user: User = Depends(require_role(UserRole.OWNER, UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
    _csrf: bool = Depends(verify_csrf),
) -> SubscriptionResponse:
    """Cancel a subscription"""
    sub = await SubscriptionService.get_subscription_with_plan(db, subscription_id, current_user.practice_id)
    if not sub:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Subscription not found")
    if sub.status in [SubscriptionStatus.CANCELED, SubscriptionStatus.EXPIRED, SubscriptionStatus.UNPAID]:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Subscription already canceled")

    # Cancel Stripe subscription using service (fail closed if Stripe was configured and failed)
    success = await SubscriptionService.cancel_stripe_subscription(sub, cancel_data.cancel_at_period_end)
    if settings.STRIPE_API_KEY and sub.stripe_subscription_id and not success:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to cancel subscription with payment processor. Please try again later.",
        )

    # Update local state
    sub.cancel_at_period_end = cancel_data.cancel_at_period_end
    sub.cancellation_reason = cancel_data.reason
    sub.cancellation_feedback = cancel_data.feedback

    if not cancel_data.cancel_at_period_end:
        sub.status = SubscriptionStatus.CANCELED
        sub.canceled_at = datetime.now(timezone.utc)

    await log_audit_event(
        db, current_user, "cancel_subscription", "subscription", subscription_id, request,
        {"cancel_at_period_end": cancel_data.cancel_at_period_end, "reason": cancel_data.reason}
    )

    await db.commit()
    await db.refresh(sub)
    return sub


@router.post("/{subscription_id}/pause", response_model=SubscriptionResponse)
async def pause_subscription(
    subscription_id: UUID,
    pause_data: SubscriptionPause,
    request: Request,
    current_user: User = Depends(require_role(UserRole.OWNER, UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
    _csrf: bool = Depends(verify_csrf),
) -> SubscriptionResponse:
    """Pause a subscription"""
    sub = await SubscriptionService.get_subscription_with_plan(db, subscription_id, current_user.practice_id)
    if not sub:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Subscription not found")
    if sub.status != SubscriptionStatus.ACTIVE:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Can only pause active subscriptions")

    # Do not advance local access state when the billing provider rejected or
    # could not perform the pause. A retry remains safe and observable.
    paused = await SubscriptionService.pause_stripe_subscription(sub)
    if not paused:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Billing provider did not pause the subscription",
        )

    sub.status = SubscriptionStatus.PAUSED
    sub.paused_at = datetime.now(timezone.utc)
    sub.paused_until = pause_data.paused_until

    await db.commit()
    await db.refresh(sub)
    return sub


@router.post("/{subscription_id}/resume", response_model=SubscriptionResponse)
async def resume_subscription(
    subscription_id: UUID,
    current_user: User = Depends(require_role(UserRole.OWNER, UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
    _csrf: bool = Depends(verify_csrf),
) -> SubscriptionResponse:
    """Resume a paused subscription"""
    sub = await SubscriptionService.get_subscription_with_plan(db, subscription_id, current_user.practice_id)
    if not sub:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Subscription not found")
    if sub.status != SubscriptionStatus.PAUSED:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Can only resume paused subscriptions")

    # Do not reactivate local access unless the processor confirms resume.
    resumed = await SubscriptionService.resume_stripe_subscription(sub)
    if not resumed:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Billing provider did not resume the subscription",
        )

    sub.status = SubscriptionStatus.ACTIVE
    sub.paused_at = None
    sub.paused_until = None

    await db.commit()
    await db.refresh(sub)
    return sub


@router.post("/{subscription_id}/change-plan", response_model=SubscriptionResponse)
async def change_plan(
    subscription_id: UUID,
    change_data: SubscriptionChangePlan,
    request: Request,
    current_user: User = Depends(require_role(UserRole.OWNER, UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
    _csrf: bool = Depends(verify_csrf),
) -> SubscriptionResponse:
    """Change to a different subscription plan with proration"""
    sub = await SubscriptionService.get_subscription_with_plan(db, subscription_id, current_user.practice_id)
    if not sub:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Subscription not found")

    plan_result = await db.execute(
        select(SubscriptionPlan).where(
            SubscriptionPlan.id == change_data.new_plan_id,
            (SubscriptionPlan.practice_id.is_(None) | (SubscriptionPlan.practice_id == current_user.practice_id)),
        )
    )
    new_plan = plan_result.scalar_one_or_none()
    if not new_plan:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="New plan not found")

    # Change plan using service
    try:
        proration_amount = await SubscriptionService.change_plan(
            db, sub, new_plan, change_data.proration_behavior
        )
    except (ValueError, TypeError, SQLAlchemyError) as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    await log_audit_event(
        db, current_user, "change_plan", "subscription", subscription_id, request,
        {"old_plan": str(sub.plan_id), "new_plan": str(new_plan.id), "proration": str(proration_amount)}
    )

    await db.commit()
    await db.refresh(sub)
    return sub


@router.post("/{subscription_id}/usage", response_model=UsageRecordResponse)
async def record_usage(
    subscription_id: UUID,
    usage_data: UsageRecordCreate,
    request: Request,
    current_user: User = Depends(require_role(UserRole.OWNER, UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
    _csrf: bool = Depends(verify_csrf),
) -> UsageRecordResponse:
    """Record usage for usage-based billing"""
    sub = await SubscriptionService.get_subscription_with_plan(db, subscription_id, current_user.practice_id)
    if not sub:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Subscription not found")

    if not sub.plan or not sub.plan.is_usage_based:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Plan is not usage-based")

    # Record usage using service
    try:
        record = await SubscriptionService.record_usage(
            db, sub, usage_data.quantity, usage_data.description, usage_data.metadata
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    return record


@router.get("/{subscription_id}/usage", response_model=UsageResponse)
async def get_usage(
    subscription_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UsageResponse:
    """Get usage details for current billing period"""
    sub = await SubscriptionService.get_subscription_with_plan(db, subscription_id, current_user.practice_id)
    if not sub:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Subscription not found")

    # Get usage records using service
    records = await SubscriptionService.get_usage_records(db, subscription_id, sub.current_period_start)

    return UsageResponse(
        subscription_id=subscription_id,
        period_start=sub.current_period_start or datetime.now(timezone.utc),
        period_end=sub.current_period_end or datetime.now(timezone.utc),
        records=records,
        summaries=[],
    )


@router.get("/{subscription_id}/dunning", response_model=DunningEventList)
async def get_dunning_events(
    subscription_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> DunningEventList:
    """Get dunning events for subscription"""
    from app.models.subscription import DunningEvent

    # Tenant scoping: only expose dunning events for subscriptions that
    # belong to the caller's practice.
    result = await db.execute(
        select(DunningEvent)
        .join(Subscription, Subscription.id == DunningEvent.subscription_id)
        .where(
            DunningEvent.subscription_id == subscription_id,
            Subscription.practice_id == current_user.practice_id,
        )
        .order_by(DunningEvent.attempt_number)
    )
    events = result.scalars().all()
    return DunningEventList(events=events, total=len(events))


@router.get("/{subscription_id}/proration-preview")
async def preview_proration(
    subscription_id: UUID,
    new_plan_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Preview proration amount for plan change"""
    sub = await SubscriptionService.get_subscription_with_plan(db, subscription_id, current_user.practice_id)
    if not sub:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Subscription not found")

    old_plan = sub.plan
    if not old_plan:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Current plan not found")

    new_plan_result = await db.execute(
        select(SubscriptionPlan).where(
            SubscriptionPlan.id == new_plan_id,
            (SubscriptionPlan.practice_id.is_(None) | (SubscriptionPlan.practice_id == current_user.practice_id)),
        )
    )
    new_plan = new_plan_result.scalar_one_or_none()
    if not new_plan:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="New plan not found")

    now = datetime.now(timezone.utc)
    if sub.current_period_end:
        days_remaining = int((sub.current_period_end - now).total_seconds() / 86400)
        total_days = int((sub.current_period_end - (sub.current_period_start or now)).total_seconds() / 86400)
    else:
        days_remaining = 30
        total_days = 30

    amount = SubscriptionService.calculate_proration_amount(old_plan.amount, new_plan.amount, days_remaining, total_days)

    # Quantize to cents before serialization: the proration amount is an
    # unquantized division result and SQLite round-trips Numeric through
    # binary floats, so a raw float() can surface as e.g. 3.3333333333 or
    # 19.990000000000002 on the wire.
    cent = Decimal("0.01")

    def _money(value) -> float:
        return float(Decimal(str(value)).quantize(cent))

    return {
        "subscription_id": str(subscription_id),
        "old_plan": {"name": old_plan.name, "amount": _money(old_plan.amount)},
        "new_plan": {"name": new_plan.name, "amount": _money(new_plan.amount)},
        "days_remaining": days_remaining,
        "total_days": total_days,
        "proration_amount": _money(amount),
        "proration_credit": amount > 0,
        "effective_immediately": True,
    }


@router.post("/dunning/process")
async def process_dunning(
    background_tasks: BackgroundTasks,
    current_user: User = Depends(require_role(UserRole.OWNER, UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
    _csrf: bool = Depends(verify_csrf),
) -> APIResponse:
    """Run dunning process for past-due subscriptions.

    M-9 / H-6 FIX: acquire the same ``process-dunning`` advisory lock
    the Celery beat uses so the manual endpoint and the hourly sweep
    cannot run simultaneously and double-charge customers. The lock is
    Postgres-only (SQLite returns True immediately per
    ``_try_acquire_task_lock``), so dev/test on SQLite keeps working.
    """
    from app.core.tasks import _try_acquire_task_lock_async

    if not await _try_acquire_task_lock_async(db, "process-dunning"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Another dunning sweep is already running; the scheduler "
                "and this endpoint cannot run simultaneously. Retry "
                "in a few minutes."
            ),
        )
    result = await SubscriptionBillingService.process_dunning(
        db, background_tasks, practice_id=current_user.practice_id
    )
    return APIResponse(success=True, data=result)


# ======================= Stripe Webhook Handler =======================

@router.post("/webhooks/stripe")
async def stripe_subscription_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> APIResponse:
    """Handle Stripe webhooks for subscription events"""
    from app.core.webhook_security import construct_stripe_event, WebhookVerificationError

    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")

    try:
        event = construct_stripe_event(payload, sig_header)
    except WebhookVerificationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid webhook signature") from exc

    try:
        success = await SubscriptionWebhookHandler.process_webhook_event(db, event)
    except WebhookDeduplicationUnavailable as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Webhook processing temporarily unavailable",
            headers={"Retry-After": "5"},
        ) from exc
    except Exception as exc:
        logger.error(f"Unhandled error in webhook processing: {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error processing webhook event",
        ) from exc

    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to process webhook event",
        )

    return APIResponse(success=True, message="Webhook processed")


@router.get("/{subscription_id}/invoice-history")
async def get_invoice_history(
    subscription_id: UUID,
    limit: int = Query(50, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Get invoice history for a subscription from Stripe"""
    import stripe as stripe_lib

    sub = await SubscriptionService.get_subscription_with_plan(db, subscription_id, current_user.practice_id)
    if not sub:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Subscription not found")

    if not settings.STRIPE_API_KEY or not sub.stripe_subscription_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Stripe not configured")

    try:
        stripe_lib.api_key = settings.STRIPE_API_KEY
        invoices = stripe_lib.Invoice.list(
            subscription=sub.stripe_subscription_id,
            limit=limit,
            status="all",
        )
        return {
            "subscription_id": str(subscription_id),
            "invoices": [
                {
                    "id": inv["id"],
                    "number": inv.get("number"),
                    # Display-only Stripe cents -> dollars quantized HALF_UP.
                    "amount_due": float((Decimal(str(inv.get("amount_due", 0))) / 100).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)),
                    "amount_paid": float((Decimal(str(inv.get("amount_paid", 0))) / 100).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)),
                    "status": inv.get("status"),
                    "created": inv.get("created"),
                    "hosted_invoice_url": inv.get("hosted_invoice_url"),
                }
                for inv in invoices.get("data", [])
            ],
        }
    except (ValueError, TypeError, KeyError) as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Stripe error: {str(e)}")


@router.post("/usage-billing/submit")
async def submit_usage_batch(
    usage_items: List[UsageRecordCreate],
    subscription_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    _csrf: bool = Depends(verify_csrf),
) -> APIResponse:
    """Submit multiple usage records at once"""
    sub = await SubscriptionService.get_subscription_with_plan(db, subscription_id, current_user.practice_id)
    if not sub:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Subscription not found")

    if not sub.plan or not sub.plan.is_usage_based:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Plan is not usage-based",
        )

    # Edge case: validate every quantity up front so a single invalid item
    # cannot partially commit a batch (each record_usage call commits).
    for usage in usage_items:
        if usage.quantity is None or usage.quantity <= 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Usage quantity must be a positive number",
            )

    records_created = 0
    for usage in usage_items:
        await SubscriptionService.record_usage(
            db, sub, usage.quantity, usage.description, usage.metadata
        )
        records_created += 1

    return APIResponse(success=True, data={"records_created": records_created})