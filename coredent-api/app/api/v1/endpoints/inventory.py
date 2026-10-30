"""
Inventory Endpoints
CRUD operations for inventory management
"""

from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, require_role, verify_csrf
from app.core.audit import log_audit_event
from app.core.business_time import (
    DateRangeError,
    get_practice_timezone,
    resolve_instant_range,
)
from app.core.database import get_db
from app.models.inventory import (
    InventoryAlert,
    InventoryAlertType,
    InventoryCategory,
    InventoryItem,
    InventoryTransaction,
    InventoryUnit,
    Supplier,
)
from app.models.user import User, UserRole

router = APIRouter()

# H4 FIX: explicit writable-field allowlists — client dicts no longer reach
# ORM constructors/setattr unfiltered (previously id/practice_id/user_id and
# unknown keys were settable or crashed with duplicate-kwarg TypeErrors).
_ITEM_WRITABLE_FIELDS = (
    "name", "description", "sku", "barcode", "category", "unit",
    "units_per_package", "current_quantity", "minimum_quantity",
    "reorder_quantity", "maximum_quantity", "unit_cost", "unit_price",
    "storage_location", "track_expiration", "expiration_warning_days",
    "supplier_name", "supplier_item_code", "is_active", "is_trackable",
)

_TRANSACTION_TYPES = {"IN", "OUT", "ADJUST", "RETURN", "EXPIRE"}
_TRANSACTION_WRITABLE_FIELDS = (
    "reference_type", "reference_id", "unit_cost", "total_cost", "notes",
)

_SUPPLIER_WRITABLE_FIELDS = (
    "name", "contact_name", "email", "phone", "fax", "website",
    "address_line1", "address_line2", "city", "state", "zip_code",
    "account_number", "payment_terms", "is_active", "notes",
)

_DEFAULT_PAGE_SIZE = 50
_MAX_PAGE_SIZE = 100


def _pagination_metadata(*, count: int, total: int, page: int, limit: int) -> dict:
    """Return additive metadata while preserving each legacy list wrapper."""
    return {
        "count": count,
        "total": total,
        "page": page,
        "limit": limit,
        "pages": (total + limit - 1) // limit,
    }


def _escape_like(value: str) -> str:
    """Escape LIKE wildcards so user input cannot force full scans."""
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _coerce_enum(enum_cls, value):
    """Coerce a client string to an enum member; None passes through."""
    if value is None:
        return None
    if isinstance(value, enum_cls):
        return value
    try:
        return enum_cls(str(value))
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid value '{value}' (expected one of: "
                   f"{', '.join(m.value for m in enum_cls)})",
        )


def _supplier_to_dict(supplier: Supplier) -> dict:
    return {
        "id": str(supplier.id),
        "practice_id": str(supplier.practice_id),
        "name": supplier.name,
        "contact_name": supplier.contact_name,
        "email": supplier.email,
        "phone": supplier.phone,
        "fax": supplier.fax,
        "website": supplier.website,
        "address_line1": supplier.address_line1,
        "address_line2": supplier.address_line2,
        "city": supplier.city,
        "state": supplier.state,
        "zip_code": supplier.zip_code,
        "account_number": supplier.account_number,
        "payment_terms": supplier.payment_terms,
        "is_active": supplier.is_active,
        "notes": supplier.notes,
        "created_at": supplier.created_at.isoformat() if supplier.created_at else None,
        "updated_at": supplier.updated_at.isoformat() if supplier.updated_at else None,
    }


def _transaction_to_dict(txn: InventoryTransaction) -> dict:
    return {
        "id": str(txn.id),
        "item_id": str(txn.item_id),
        "practice_id": str(txn.practice_id),
        "user_id": str(txn.user_id) if txn.user_id else None,
        "transaction_type": txn.transaction_type,
        "quantity": txn.quantity,
        "previous_quantity": txn.previous_quantity,
        "new_quantity": txn.new_quantity,
        "reference_type": txn.reference_type,
        "reference_id": str(txn.reference_id) if txn.reference_id else None,
        "unit_cost": str(txn.unit_cost) if txn.unit_cost is not None else None,
        "total_cost": str(txn.total_cost) if txn.total_cost is not None else None,
        "notes": txn.notes,
        "created_at": txn.created_at.isoformat() if txn.created_at else None,
    }


def _alert_to_dict(alert: InventoryAlert) -> dict:
    return {
        "id": str(alert.id),
        "item_id": str(alert.item_id),
        "practice_id": str(alert.practice_id),
        "alert_type": alert.alert_type.value if alert.alert_type else None,
        "message": alert.message,
        "is_resolved": alert.is_resolved,
        "resolved_at": alert.resolved_at.isoformat() if alert.resolved_at else None,
        "resolved_by": str(alert.resolved_by) if alert.resolved_by else None,
        "created_at": alert.created_at.isoformat() if alert.created_at else None,
    }


def _item_to_dict(item: InventoryItem) -> dict:
    """Serialize an InventoryItem to a dict for JSON response."""
    return {
        "id": str(item.id),
        "name": item.name,
        "description": item.description,
        "sku": item.sku,
        "barcode": item.barcode,
        "category": item.category.value if item.category else None,
        "unit": item.unit.value if item.unit else None,
        "units_per_package": item.units_per_package,
        "current_quantity": item.current_quantity,
        "minimum_quantity": item.minimum_quantity,
        "reorder_quantity": item.reorder_quantity,
        "maximum_quantity": item.maximum_quantity,
        "unit_cost": str(item.unit_cost) if item.unit_cost is not None else None,
        "unit_price": str(item.unit_price) if item.unit_price is not None else None,
        "storage_location": item.storage_location,
        "track_expiration": item.track_expiration,
        "expiration_warning_days": item.expiration_warning_days,
        "supplier_name": item.supplier_name,
        "supplier_item_code": item.supplier_item_code,
        "is_active": item.is_active,
        "is_trackable": item.is_trackable,
        "created_at": item.created_at.isoformat() if item.created_at else None,
        "updated_at": item.updated_at.isoformat() if item.updated_at else None,
    }


# Inventory Item Endpoints

@router.get("/items/")
async def list_inventory_items(
    category: Optional[InventoryCategory] = Query(None, description="Filter by category"),
    search: Optional[str] = Query(None, description="Search by name or SKU"),
    low_stock: Optional[bool] = Query(None, description="Filter low stock items"),
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(
        _DEFAULT_PAGE_SIZE,
        ge=1,
        le=_MAX_PAGE_SIZE,
        description="Page size (max 100)",
    ),
    request: Request = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """List one practice's inventory with bounded, additive pagination."""
    filters = [InventoryItem.practice_id == current_user.practice_id]

    if category:
        filters.append(InventoryItem.category == category)

    if search:
        # Parameterized + wildcard-escaped (L2)
        search_pattern = f"%{_escape_like(search)}%"
        filters.append(
            (InventoryItem.name.ilike(search_pattern, escape="\\"))
            | (InventoryItem.sku.ilike(search_pattern, escape="\\"))
        )

    if low_stock:
        # Equivalent to InventoryItem.is_low_stock, evaluated in SQL before paging.
        filters.append(InventoryItem.current_quantity <= InventoryItem.minimum_quantity)

    total = (
        await db.execute(select(func.count(InventoryItem.id)).where(*filters))
    ).scalar_one()
    result = await db.execute(
        select(InventoryItem)
        .where(*filters)
        .order_by(InventoryItem.name, InventoryItem.id)
        .limit(limit)
        .offset((page - 1) * limit)
    )
    items = result.scalars().all()

    # Audit Logging (Practice Management)
    await log_audit_event(
        db, current_user, "list_inventory", "inventory", None, request
    )
    await db.commit()

    return {
        "items": [_item_to_dict(item) for item in items],
        **_pagination_metadata(
            count=len(items),
            total=total,
            page=page,
            limit=limit,
        ),
    }


@router.get("/items/{item_id}")
async def get_inventory_item(
    item_id: UUID,
    request: Request = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Get inventory item by ID
    """
    result = await db.execute(
        select(InventoryItem).where(
            InventoryItem.id == item_id,
            InventoryItem.practice_id == current_user.practice_id,
        )
    )
    item = result.scalar_one_or_none()

    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Inventory item not found",
        )

    # Audit Logging
    await log_audit_event(
        db, current_user, "view_inventory_item", "inventory_item", item.id, request
    )
    await db.commit()

    return _item_to_dict(item)


@router.post("/items/")
async def create_inventory_item(
    item_data: dict,
    current_user: User = Depends(require_role(UserRole.OWNER, UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
    _csrf: bool = Depends(verify_csrf),
) -> dict:
    """
    Create new inventory item
    """
    fields = {k: v for k, v in item_data.items() if k in _ITEM_WRITABLE_FIELDS}
    if not fields.get("name"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="name is required",
        )
    fields["category"] = _coerce_enum(InventoryCategory, fields.get("category"))
    fields["unit"] = _coerce_enum(InventoryUnit, fields.get("unit"))

    item = InventoryItem(
        practice_id=current_user.practice_id,
        **fields
    )
    db.add(item)
    await db.commit()
    await db.refresh(item)

    return _item_to_dict(item)


@router.put("/items/{item_id}")
async def update_inventory_item(
    item_id: UUID,
    item_data: dict,
    current_user: User = Depends(require_role(UserRole.OWNER, UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
    _csrf: bool = Depends(verify_csrf),
) -> dict:
    """
    Update inventory item
    """
    result = await db.execute(
        select(InventoryItem).where(
            InventoryItem.id == item_id,
            InventoryItem.practice_id == current_user.practice_id,
        )
    )
    item = result.scalar_one_or_none()

    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Inventory item not found",
        )

    for field in _ITEM_WRITABLE_FIELDS:
        if field not in item_data:
            continue
        value = item_data[field]
        if field == "category":
            value = _coerce_enum(InventoryCategory, value)
        elif field == "unit":
            value = _coerce_enum(InventoryUnit, value)
        setattr(item, field, value)

    await db.commit()
    await db.refresh(item)

    return _item_to_dict(item)


@router.delete("/items/{item_id}")
async def delete_inventory_item(
    item_id: UUID,
    current_user: User = Depends(require_role(UserRole.OWNER, UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
    _csrf: bool = Depends(verify_csrf),
) -> dict:
    """
    Delete inventory item
    """
    result = await db.execute(
        select(InventoryItem).where(
            InventoryItem.id == item_id,
            InventoryItem.practice_id == current_user.practice_id,
        )
    )
    item = result.scalar_one_or_none()

    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Inventory item not found",
        )

    await db.delete(item)
    await db.commit()

    return {"message": "Inventory item deleted successfully"}


# Inventory Transaction Endpoints

@router.get("/transactions/")
async def list_inventory_transactions(
    item_id: Optional[str] = Query(None, description="Filter by item"),
    transaction_type: Optional[str] = Query(None, description="Filter by transaction type"),
    start_date: Optional[datetime] = Query(
        None,
        description="UTC start timestamp for filtering",
    ),
    end_date: Optional[datetime] = Query(
        None,
        description="UTC end timestamp (exclusive) for filtering",
    ),
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(
        _DEFAULT_PAGE_SIZE,
        ge=1,
        le=_MAX_PAGE_SIZE,
        description="Page size (max 100)",
    ),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """List a bounded, stable page of one practice's inventory transactions."""
    tz = await get_practice_timezone(db, current_user.practice_id)
    try:
        window = resolve_instant_range(tz, start_date, end_date, max_days=366)
    except DateRangeError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    filters = [
        InventoryTransaction.practice_id == current_user.practice_id,
        InventoryTransaction.created_at >= window.start_utc,
        InventoryTransaction.created_at < window.end_utc,
    ]

    if item_id:
        filters.append(InventoryTransaction.item_id == item_id)

    if transaction_type:
        filters.append(InventoryTransaction.transaction_type == transaction_type)

    total = (
        await db.execute(select(func.count(InventoryTransaction.id)).where(*filters))
    ).scalar_one()
    result = await db.execute(
        select(InventoryTransaction)
        .where(*filters)
        .order_by(InventoryTransaction.created_at.desc(), InventoryTransaction.id.desc())
        .limit(limit)
        .offset((page - 1) * limit)
    )
    transactions = result.scalars().all()

    return {
        "transactions": transactions,
        **_pagination_metadata(
            count=len(transactions),
            total=total,
            page=page,
            limit=limit,
        ),
    }


@router.post("/transactions/")
async def create_inventory_transaction(
    request: Request,
    transaction_data: dict,
    current_user: User = Depends(require_role(UserRole.OWNER, UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
    _csrf: bool = Depends(verify_csrf),
) -> dict:
    """
    Create inventory transaction (add or remove stock)
    """
    # Get the item with row lock. Gate on row_locks_supported() for the same
    # reason as the billing endpoints: on SQLite the FOR UPDATE clause is
    # silently ignored anyway, and the helper warns loudly about the
    # degradation instead of leaving it invisible.
    from app.core.database import row_locks_supported

    item_stmt = select(InventoryItem).where(
        InventoryItem.id == transaction_data.get("item_id"),
        InventoryItem.practice_id == current_user.practice_id,
    )
    if row_locks_supported():
        item_stmt = item_stmt.with_for_update()
    result = await db.execute(item_stmt)
    item = result.scalar_one_or_none()

    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Inventory item not found",
        )

    # Calculate new quantity
    quantity = transaction_data.get("quantity", 0)
    transaction_type = transaction_data.get("transaction_type")
    if transaction_type not in _TRANSACTION_TYPES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"transaction_type must be one of: {', '.join(sorted(_TRANSACTION_TYPES))}",
        )
    # M-07 FIX: quantities are magnitudes. A negative "IN" reduced stock and a
    # negative "OUT" increased it, silently bypassing the stock checks below;
    # direction is expressed by transaction_type, never by the sign.
    if isinstance(quantity, bool) or not isinstance(quantity, (int, float)) or quantity < 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="quantity must be a non-negative number",
        )
    previous_quantity = item.current_quantity

    if transaction_type == "IN":
        new_quantity = previous_quantity + quantity
    elif transaction_type in ("OUT", "RETURN", "EXPIRE"):
        # M-07 FIX: RETURN (to vendor) and EXPIRE (disposal) are stock exits,
        # like OUT -- they previously fell into the ADJUST branch and REPLACED
        # the stock level with the raw input.
        new_quantity = previous_quantity - quantity
        if new_quantity < 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Insufficient stock",
            )
    else:  # ADJUST sets the absolute level, which can never be negative.
        new_quantity = quantity
        if new_quantity < 0:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Adjusted quantity cannot be negative",
            )

    # Update item quantity
    item.current_quantity = new_quantity

    # H4 FIX: only writable reference/cost/notes fields come from the client;
    # item_id/practice_id/user_id and the quantity bookkeeping are set here.
    fields = {k: v for k, v in transaction_data.items() if k in _TRANSACTION_WRITABLE_FIELDS}
    transaction = InventoryTransaction(
        practice_id=current_user.practice_id,
        user_id=current_user.id,
        item_id=item.id,
        transaction_type=transaction_type,
        quantity=quantity,
        previous_quantity=previous_quantity,
        new_quantity=new_quantity,
        **fields
    )
    db.add(transaction)

    # Check for low stock alert
    if item.needs_reorder:
        # Create alert
        alert = InventoryAlert(
            item_id=item.id,
            practice_id=current_user.practice_id,
            alert_type=InventoryAlertType.REORDER_POINT,
            message=f"Item {item.name} is at or below reorder point"
        )
        db.add(alert)

    # Audit Logging (Critical Stock Transaction)
    await log_audit_event(
        db, current_user, "inventory_adjustment", "inventory_transaction", transaction.item_id, request,
        {"type": transaction_type, "qty": quantity}
    )

    await db.commit()
    await db.refresh(transaction)

    return _transaction_to_dict(transaction)


# Supplier Endpoints

@router.get("/suppliers/")
async def list_suppliers(
    request: Request,
    search: Optional[str] = Query(None, description="Search by name"),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(
        _DEFAULT_PAGE_SIZE,
        ge=1,
        le=_MAX_PAGE_SIZE,
        description="Page size (max 100)",
    ),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """List one practice's suppliers with additive pagination metadata."""
    filters = [Supplier.practice_id == current_user.practice_id]

    if is_active is not None:
        filters.append(Supplier.is_active == is_active)

    if search:
        # Parameterized + wildcard-escaped (L2)
        search_pattern = f"%{_escape_like(search)}%"
        filters.append(Supplier.name.ilike(search_pattern, escape="\\"))

    total = (await db.execute(select(func.count(Supplier.id)).where(*filters))).scalar_one()
    result = await db.execute(
        select(Supplier)
        .where(*filters)
        .order_by(Supplier.name, Supplier.id)
        .limit(limit)
        .offset((page - 1) * limit)
    )
    suppliers = result.scalars().all()

    # HIPAA: Log supplier list access
    await log_audit_event(
        db, current_user, "list_suppliers", "inventory", None, request
    )
    await db.commit()

    return {
        "suppliers": [_supplier_to_dict(supplier) for supplier in suppliers],
        **_pagination_metadata(
            count=len(suppliers),
            total=total,
            page=page,
            limit=limit,
        ),
    }


@router.post("/suppliers/")
async def create_supplier(
    supplier_data: dict,
    current_user: User = Depends(require_role(UserRole.OWNER, UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
    _csrf: bool = Depends(verify_csrf),
) -> dict:
    """
    Create new supplier
    """
    fields = {k: v for k, v in supplier_data.items() if k in _SUPPLIER_WRITABLE_FIELDS}
    if not fields.get("name"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="name is required",
        )
    supplier = Supplier(
        practice_id=current_user.practice_id,
        **fields
    )
    db.add(supplier)
    await db.commit()
    await db.refresh(supplier)

    return _supplier_to_dict(supplier)


# Alerts Endpoints

@router.get("/alerts/")
async def list_inventory_alerts(
    item_id: Optional[str] = Query(None, description="Filter by item"),
    alert_type: Optional[InventoryAlertType] = Query(None, description="Filter by alert type"),
    is_resolved: Optional[bool] = Query(None, description="Filter by resolved status"),
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(
        _DEFAULT_PAGE_SIZE,
        ge=1,
        le=_MAX_PAGE_SIZE,
        description="Page size (max 100)",
    ),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """List one practice's inventory alerts with additive pagination metadata."""
    filters = [InventoryAlert.practice_id == current_user.practice_id]

    if item_id:
        filters.append(InventoryAlert.item_id == item_id)

    if alert_type:
        filters.append(InventoryAlert.alert_type == alert_type)

    if is_resolved is not None:
        filters.append(InventoryAlert.is_resolved == is_resolved)

    total = (
        await db.execute(select(func.count(InventoryAlert.id)).where(*filters))
    ).scalar_one()
    result = await db.execute(
        select(InventoryAlert)
        .where(*filters)
        .order_by(InventoryAlert.created_at.desc(), InventoryAlert.id.desc())
        .limit(limit)
        .offset((page - 1) * limit)
    )
    alerts = result.scalars().all()

    return {
        "alerts": [_alert_to_dict(alert) for alert in alerts],
        **_pagination_metadata(
            count=len(alerts),
            total=total,
            page=page,
            limit=limit,
        ),
    }


@router.post("/alerts/{alert_id}/resolve")
async def resolve_inventory_alert(
    alert_id: UUID,
    current_user: User = Depends(require_role(UserRole.OWNER, UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
    _csrf: bool = Depends(verify_csrf),
) -> dict:
    """
    Resolve inventory alert
    """
    result = await db.execute(
        select(InventoryAlert).where(
            InventoryAlert.id == alert_id,
            InventoryAlert.practice_id == current_user.practice_id,
        )
    )
    alert = result.scalar_one_or_none()

    if not alert:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Alert not found",
        )

    alert.is_resolved = True
    alert.resolved_at = datetime.now(timezone.utc)
    alert.resolved_by = current_user.id

    await db.commit()
    await db.refresh(alert)

    return _alert_to_dict(alert)