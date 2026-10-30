"""Phase-3 regression tests for audit fixes (H-1..L-16).

Fast unit tests (no DB) pinning the surgical fixes so regressions fail loudly.
"""
from decimal import Decimal, ROUND_HALF_UP


def test_money_rounding_pinned_half_up():
    from app.services.treatment_costing import _MONEY_ROUNDING, CENT, _dec
    from app.api.v1.endpoints.billing import _MONEY_ROUNDING as BILLING_ROUND

    assert _MONEY_ROUNDING == ROUND_HALF_UP
    assert BILLING_ROUND == ROUND_HALF_UP
    # .005 edge rounds up under HALF_UP (would bank to .00 under HALF_EVEN).
    assert _dec("1.005") == Decimal("1.01")
    assert Decimal("1.005").quantize(CENT, rounding=_MONEY_ROUNDING) == Decimal("1.01")


def test_gst_splits_sum_to_tax():
    from app.api.v1.endpoints.billing import _split_gst

    cgst, sgst, igst = _split_gst(Decimal("18.00"), "N")
    assert cgst + sgst + igst == Decimal("18.00")
    assert igst == Decimal("0.00")
    # Odd cent goes to SGST so the three always sum exactly.
    cgst, sgst, igst = _split_gst(Decimal("10.01"), "N")
    assert cgst + sgst + igst == Decimal("10.01")
    cgst, sgst, igst = _split_gst(Decimal("18.00"), "Y")
    assert (cgst, sgst, igst) == (Decimal("0.00"), Decimal("0.00"), Decimal("18.00"))


def test_payment_model_scoped_unique():
    from app.models.billing import Payment

    uniques = [c for c in Payment.__table_args__ if getattr(c, "name", "") == "uq_payment_practice_transaction"]
    assert len(uniques) == 1
    cols = list(uniques[0].columns.keys())
    assert cols == ["practice_id", "transaction_id"]
    # No global unique on the column itself.
    assert Payment.__table__.c.transaction_id.unique is not True


def test_lab_inventory_scoped_uniques():
    from app.models.lab import LabInvoice
    from app.models.inventory import PurchaseOrder

    lab_names = [getattr(c, "name", "") for c in LabInvoice.__table_args__]
    assert "uq_lab_invoice_practice_number" in lab_names
    assert LabInvoice.__table__.c.invoice_number.unique is not True
    po_names = [getattr(c, "name", "") for c in PurchaseOrder.__table_args__]
    assert "uq_purchase_order_practice_number" in po_names
    assert PurchaseOrder.__table__.c.order_number.unique is not True


def test_audit_query_redaction():
    from app.main import _redacted_query

    class FakeParams(dict):
        def getlist(self, k):
            v = self.get(k)
            return [v] if v is not None else []

    q = _redacted_query(FakeParams({"phone": "555-0100", "query": "John", "skip": "0", "limit": "10"}))
    assert "555-0100" not in q
    assert "John" not in q
    assert "[REDACTED]" in q
    assert "skip=0" in q
    assert "limit=10" in q


def test_refresh_absolute_config():
    from app.core.config_simple import settings

    assert settings.REFRESH_ABSOLUTE_EXPIRE_DAYS == 30
    assert settings.REFRESH_TOKEN_EXPIRE_DAYS == 7
    assert settings.REFRESH_ABSOLUTE_EXPIRE_DAYS > settings.REFRESH_TOKEN_EXPIRE_DAYS


def test_password_min_floor(monkeypatch):
    from app.core import security
    from app.core.security import validate_password_strength

    # Even if an operator weakens PASSWORD_MIN_LENGTH to 1 via env, the floor
    # at 8 holds.
    monkeypatch.setattr(security.settings, "PASSWORD_MIN_LENGTH", 1)
    ok_short, msg = validate_password_strength("Ab1!cde")  # 7 chars, meets classes
    assert ok_short is False
    assert "8 characters" in msg


def test_stripe_interval_map_has_no_none():
    """No billing-interval mapping may produce None (crash/mis-bill risk).

    L-5 CLEANUP: the dead ``_STRIPE_INTERVAL_MAP`` in stripe.py was removed.
    The guard now targets the LIVE module-level maps in subscriptions.py that
    actually build Stripe ``recurring`` payloads, and asserts the enum's
    values are exactly the mapped keys — so an interval added to the enum
    without a Stripe mapping fails loudly here instead of silently
    falling back to monthly.
    """
    from app.api.v1.endpoints.subscriptions import (
        STRIPE_INTERVAL_COUNT,
        STRIPE_INTERVAL_MAP,
    )
    from app.models.subscription import SubscriptionInterval

    # Daily billing is unsupported by design (no DAILY enum member).
    assert "day" not in STRIPE_INTERVAL_MAP
    assert all(v is not None for v in STRIPE_INTERVAL_MAP.values())
    assert all(v is not None for v in STRIPE_INTERVAL_COUNT.values())

    # Every enum interval must have an explicit Stripe mapping and count.
    enum_values = {member.value for member in SubscriptionInterval}
    assert enum_values == set(STRIPE_INTERVAL_MAP.keys())
    assert enum_values == set(STRIPE_INTERVAL_COUNT.keys())


def test_billing_summary_has_pending_invoices():
    from app.schemas.billing import BillingSummary

    # Verify pending_invoices field exists with default 0
    fields = BillingSummary.model_fields
    assert "pending_invoices" in fields
    assert fields["pending_invoices"].default == 0


def test_practice_inbound_phone_number_column():
    from app.models.practice import Practice

    assert hasattr(Practice, "inbound_phone_number")
    col = Practice.__table__.c.inbound_phone_number
    assert col.nullable is True


def test_user_roles_coverage():
    from app.models.user import UserRole

    assert hasattr(UserRole, "ACCOUNTANT")
    assert hasattr(UserRole, "SUPER_ADMIN")
    assert hasattr(UserRole, "OWNER")
    assert hasattr(UserRole, "ADMIN")
    assert hasattr(UserRole, "DENTIST")
    assert hasattr(UserRole, "HYGIENIST")
    assert hasattr(UserRole, "FRONT_DESK")


def test_appointment_status_completed():
    from app.models.appointment import AppointmentStatus

    assert AppointmentStatus.COMPLETED.value == "completed"
