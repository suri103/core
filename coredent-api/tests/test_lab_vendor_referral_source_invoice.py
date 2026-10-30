"""Tests for lab vendor edit/delete, referral source edit/delete,
and lab invoice create/pay endpoints.
"""
import uuid
from decimal import Decimal

import pytest

from app.models.lab import Lab, LabInvoice
from app.models.referral import ReferralSource1, ReferralSource

pytestmark = pytest.mark.asyncio


class TestLabVendorEditDelete:
    async def _make_lab(self, db_session, test_practice, name="Vendor Lab"):
        lab = Lab(
            practice_id=test_practice.id,
            name=name,
            contact_name="Contact",
            email="v@example.com",
            phone="555-0000",
            is_active=True,
            is_preferred=False,
        )
        db_session.add(lab)
        await db_session.commit()
        await db_session.refresh(lab)
        return lab

    async def test_update_lab_vendor(self, client, auth_headers, db_session, test_practice):
        lab = await self._make_lab(db_session, test_practice)
        response = await client.put(
            f"/api/v1/labs/vendors/{lab.id}",
            headers=auth_headers,
            json={"name": "Updated Lab", "is_preferred": True},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Updated Lab"
        assert data["is_preferred"] is True

    async def test_delete_lab_vendor_hides_from_list(
        self, client, auth_headers, db_session, test_practice
    ):
        lab = await self._make_lab(db_session, test_practice)
        delete = await client.delete(f"/api/v1/labs/vendors/{lab.id}", headers=auth_headers)
        assert delete.status_code == 200

        listing = await client.get("/api/v1/labs/vendors/", headers=auth_headers)
        assert listing.status_code == 200
        ids = [v["id"] for v in listing.json()["labs"]]
        assert str(lab.id) not in ids

    async def test_update_other_tenant_vendor_404(
        self, client, auth_headers, db_session, other_practice
    ):
        lab = Lab(
            practice_id=other_practice.id,
            name="Other" + uuid.uuid4().hex[:6],
        )
        db_session.add(lab)
        await db_session.commit()
        response = await client.put(
            f"/api/v1/labs/vendors/{lab.id}", headers=auth_headers, json={"name": "nope"}
        )
        assert response.status_code == 404


class TestReferralSourceEditDelete:
    async def test_update_and_delete_referral_source(
        self, client, auth_headers, db_session, test_practice
    ):
        source = ReferralSource1(
            practice_id=test_practice.id,
            name="Dr. Smith",
            source_type=ReferralSource.OTHER_DENTIST,
            is_active=True,
        )
        db_session.add(source)
        await db_session.commit()
        await db_session.refresh(source)

        upd = await client.put(
            f"/api/v1/referrals/sources/{source.id}",
            headers=auth_headers,
            json={"name": "Dr. Jones", "specialty": "Oral Surgery"},
        )
        assert upd.status_code == 200
        assert upd.json()["name"] == "Dr. Jones"

        rem = await client.delete(
            f"/api/v1/referrals/sources/{source.id}", headers=auth_headers
        )
        assert rem.status_code == 200

        listing = await client.get("/api/v1/referrals/sources/", headers=auth_headers)
        ids = [s["id"] for s in listing.json()["sources"]]
        assert str(source.id) not in ids


class TestLabInvoiceMoney:
    async def _make_lab(self, db_session, test_practice):
        lab = Lab(
            practice_id=test_practice.id, name="Invoice Lab" + uuid.uuid4().hex[:4]
        )
        db_session.add(lab)
        await db_session.commit()
        await db_session.refresh(lab)
        return lab

    async def test_create_lab_invoice_computes_total(
        self, client, auth_headers, db_session, test_practice
    ):
        lab = await self._make_lab(db_session, test_practice)
        response = await client.post(
            "/api/v1/labs/invoices/",
            headers=auth_headers,
            json={
                "lab_id": str(lab.id),
                "subtotal": "100.00",
                "tax": "10.00",
                "shipping": "5.00",
                "discount": "2.00",
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["total"] == "113.00"
        # Money fields are serialized as fixed 2dp strings (billing
        # convention) — zero is "0.00", not bare "0".
        assert data["amount_paid"] == "0.00"
        assert data["status"] == "pending"
        assert data["invoice_number"].startswith("LABINV-")
        return data, lab

    async def test_pay_lab_invoice_full(self, client, auth_headers, db_session, test_practice):
        created, lab = await self.test_create_lab_invoice_computes_total(
            client, auth_headers, db_session, test_practice
        )
        response = await client.post(
            f"/api/v1/labs/invoices/{created['id']}/pay",
            headers=auth_headers,
            json={"transaction_id": str(uuid.uuid4()), "amount": "113.00"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "paid"
        assert data["amount_paid"] == "113.00"

    async def test_pay_lab_invoice_partial(self, client, auth_headers, db_session, test_practice):
        created, _ = await self.test_create_lab_invoice_computes_total(
            client, auth_headers, db_session, test_practice
        )
        response = await client.post(
            f"/api/v1/labs/invoices/{created['id']}/pay",
            headers=auth_headers,
            json={"transaction_id": str(uuid.uuid4()), "amount": "50.00"},
        )
        assert response.status_code == 200
        assert response.json()["status"] == "partial"

    async def test_pay_lab_invoice_rejects_overpayment(
        self, client, auth_headers, db_session, test_practice
    ):
        created, _ = await self.test_create_lab_invoice_computes_total(
            client, auth_headers, db_session, test_practice
        )
        response = await client.post(
            f"/api/v1/labs/invoices/{created['id']}/pay",
            headers=auth_headers,
            json={"transaction_id": str(uuid.uuid4()), "amount": "999.00"},
        )
        assert response.status_code == 409

    async def test_pay_other_tenant_invoice_404(
        self, client, auth_headers, db_session, other_practice
    ):
        inv = LabInvoice(
            practice_id=other_practice.id,
            lab_id=uuid.uuid4(),
            invoice_number="LABINV-OTHER-" + uuid.uuid4().hex[:4],
            total=Decimal("10.00"),
            amount_paid=Decimal("0"),
            status="pending",
        )
        db_session.add(inv)
        await db_session.commit()
        response = await client.post(
            f"/api/v1/labs/invoices/{inv.id}/pay",
            headers=auth_headers,
            json={"transaction_id": str(uuid.uuid4()), "amount": "5.00"},
        )
        assert response.status_code == 404
