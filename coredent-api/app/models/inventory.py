"""
Inventory Models
Supply tracking, inventory management, and reorder alerts
"""

from sqlalchemy import Column, String, DateTime, ForeignKey, Enum, Text, Numeric, Integer, Boolean, UniqueConstraint, CheckConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid
import enum

from app.core.base import Base


class InventoryCategory(str, enum.Enum):
    """Inventory categories"""
    SUPPLIES = "supplies"
    EQUIPMENT = "equipment"
    MEDICATIONS = "medications"
    RESTORATIVE = "restorative"
    SURGICAL = "surgical"
    DISPOSABLE = "disposable"
    OTHER = "other"


class InventoryUnit(str, enum.Enum):
    """Inventory units"""
    EACH = "each"
    BOX = "box"
    PACK = "pack"
    CASE = "case"
    GALLON = "gallon"
    LITER = "liter"


class InventoryAlertType(str, enum.Enum):
    """Types of inventory alerts"""
    LOW_STOCK = "low_stock"
    REORDER_POINT = "reorder_point"
    EXPIRING_SOON = "expiring_soon"
    EXPIRED = "expired"
    OUT_OF_STOCK = "out_of_stock"


class InventoryItem(Base):
    """Inventory item model"""
    __tablename__ = "inventory_items"
    __table_args__ = (
        UniqueConstraint('practice_id', 'sku', name='uq_practice_inventory_sku'),
        CheckConstraint('current_quantity >= 0', name='ck_inventory_current_quantity_non_negative'),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    practice_id = Column(UUID(as_uuid=True), ForeignKey("practices.id"), nullable=False)

    # Item Information
    name = Column(String(255), nullable=False)
    description = Column(Text)
    sku = Column(String(50), index=True)
    barcode = Column(String(50))
    category = Column(Enum(InventoryCategory), default=InventoryCategory.SUPPLIES)

    # Unit of Measure
    unit = Column(Enum(InventoryUnit), default=InventoryUnit.EACH)
    units_per_package = Column(Integer, default=1)

    # Stock Levels
    current_quantity = Column(Integer, default=0)
    minimum_quantity = Column(Integer, default=0)
    reorder_quantity = Column(Integer, default=0)
    maximum_quantity = Column(Integer, default=0)

    # Pricing
    unit_cost = Column(Numeric(10, 2))
    unit_price = Column(Numeric(10, 2))

    # Location
    storage_location = Column(String(100))

    # Expiration Tracking
    track_expiration = Column(Boolean, default=False)
    expiration_warning_days = Column(Integer, default=30)

    # Supplier Information
    supplier_name = Column(String(255))
    supplier_item_code = Column(String(50))

    # Status
    is_active = Column(Boolean, default=True)
    is_trackable = Column(Boolean, default=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    practice = relationship("Practice", back_populates="inventory_items")
    transactions = relationship("InventoryTransaction", back_populates="item", cascade="all, delete-orphan")
    alerts = relationship("InventoryAlert", back_populates="item", cascade="all, delete-orphan")

    @property
    def is_low_stock(self) -> bool:
        return self.current_quantity <= self.minimum_quantity

    @property
    def needs_reorder(self) -> bool:
        return self.current_quantity <= self.reorder_quantity

    def __repr__(self):
        return f"<InventoryItem {self.name} - Qty: {self.current_quantity}>"


class InventoryTransaction(Base):
    """Inventory transaction model - tracks all stock movements"""
    __tablename__ = "inventory_transactions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    item_id = Column(UUID(as_uuid=True), ForeignKey("inventory_items.id"), nullable=False)
    practice_id = Column(UUID(as_uuid=True), ForeignKey("practices.id"), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"))

    # Transaction Details
    transaction_type = Column(String(20), nullable=False)  # IN, OUT, ADJUST, RETURN, EXPIRE
    quantity = Column(Integer, nullable=False)
    previous_quantity = Column(Integer, nullable=False)
    new_quantity = Column(Integer, nullable=False)

    # Reference
    reference_type = Column(String(50))  # ORDER, PATIENT, ADJUSTMENT
    reference_id = Column(UUID(as_uuid=True))

    # Cost
    unit_cost = Column(Numeric(10, 2))
    total_cost = Column(Numeric(10, 2))

    # Notes
    notes = Column(Text)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    item = relationship("InventoryItem", back_populates="transactions")
    practice = relationship("Practice")
    user = relationship("User")

    def __repr__(self):
        return f"<InventoryTransaction {self.transaction_type} - Qty: {self.quantity}>"


class InventoryAlert(Base):
    """Inventory alert model for low stock and reorder notifications"""
    __tablename__ = "inventory_alerts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    item_id = Column(UUID(as_uuid=True), ForeignKey("inventory_items.id"), nullable=False)
    practice_id = Column(UUID(as_uuid=True), ForeignKey("practices.id"), nullable=False)

    # Alert Details
    alert_type = Column(Enum(InventoryAlertType), nullable=False)
    message = Column(Text)

    # Status
    is_resolved = Column(Boolean, default=False)
    resolved_at = Column(DateTime(timezone=True))
    resolved_by = Column(UUID(as_uuid=True), ForeignKey("users.id"))

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    item = relationship("InventoryItem", back_populates="alerts")
    practice = relationship("Practice")

    def __repr__(self):
        return f"<InventoryAlert {self.alert_type} for Item {self.item_id}>"


class Supplier(Base):
    """Supplier/vendor model"""
    __tablename__ = "suppliers"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    practice_id = Column(UUID(as_uuid=True), ForeignKey("practices.id"), nullable=False)

    # Supplier Information
    name = Column(String(255), nullable=False)
    contact_name = Column(String(100))
    email = Column(String(255))
    phone = Column(String(20))
    fax = Column(String(20))
    website = Column(String(255))

    # Address
    address_line1 = Column(String(255))
    address_line2 = Column(String(255))
    city = Column(String(100))
    state = Column(String(2))
    zip_code = Column(String(10))

    # Account Information
    account_number = Column(String(50))
    payment_terms = Column(String(50))  # Net 30, Net 60, etc.

    # Status
    is_active = Column(Boolean, default=True)
    notes = Column(Text)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    practice = relationship("Practice", back_populates="suppliers")
    purchase_orders = relationship("PurchaseOrder", back_populates="supplier")

    def __repr__(self):
        return f"<Supplier {self.name}>"


class PurchaseOrder(Base):
    """Purchase order model"""
    __tablename__ = "purchase_orders"
    __table_args__ = (
        # L-2 FIX: scope order numbers per practice like invoice numbers.
        # The previous global unique let one tenant squat/probe another's.
        UniqueConstraint(
            "practice_id",
            "order_number",
            name="uq_purchase_order_practice_number",
        ),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    practice_id = Column(UUID(as_uuid=True), ForeignKey("practices.id"), nullable=False)
    supplier_id = Column(UUID(as_uuid=True), ForeignKey("suppliers.id"), nullable=False)
    ordered_by = Column(UUID(as_uuid=True), ForeignKey("users.id"))

    # Order Information
    order_number = Column(String(50), nullable=False, index=True)
    order_date = Column(DateTime(timezone=True), server_default=func.now())
    expected_delivery = Column(DateTime(timezone=True))
    received_date = Column(DateTime(timezone=True))

    # Status
    status = Column(String(20), default="pending")  # pending, ordered, shipped, partial, received, cancelled

    # Financial
    subtotal = Column(Numeric(10, 2), default=0)
    tax = Column(Numeric(10, 2), default=0)
    shipping = Column(Numeric(10, 2), default=0)
    total = Column(Numeric(10, 2), default=0)

    # Notes
    notes = Column(Text)
    internal_notes = Column(Text)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    practice = relationship("Practice", back_populates="purchase_orders")
    supplier = relationship("Supplier", back_populates="purchase_orders")
    user = relationship("User")
    items = relationship("PurchaseOrderItem", back_populates="order")

    def __repr__(self):
        return f"<PurchaseOrder {self.order_number} - {self.status}>"


class PurchaseOrderItem(Base):
    """Purchase order item model"""
    __tablename__ = "purchase_order_items"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    order_id = Column(UUID(as_uuid=True), ForeignKey("purchase_orders.id"), nullable=False)
    item_id = Column(UUID(as_uuid=True), ForeignKey("inventory_items.id"), nullable=False)

    # Item Details
    quantity_ordered = Column(Integer, nullable=False)
    quantity_received = Column(Integer, default=0)

    # Pricing
    unit_cost = Column(Numeric(10, 2))
    total_cost = Column(Numeric(10, 2))

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    order = relationship("PurchaseOrder", back_populates="items")
    item = relationship("InventoryItem")

    def __repr__(self):
        return f"<PurchaseOrderItem {self.item_id} - Ordered: {self.quantity_ordered}>"
