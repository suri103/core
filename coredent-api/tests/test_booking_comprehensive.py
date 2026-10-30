"""
Comprehensive booking endpoint tests.
"""
import pytest
from httpx import AsyncClient

from app.models.booking import BookingPage, BookingPageStatus

pytestmark = pytest.mark.asyncio


class TestBookingPageEndpoints:
    """Booking page CRUD tests."""

    async def test_list_booking_pages(self, client: AsyncClient, auth_headers, db_session, test_practice):
        page = BookingPage(
            practice_id=test_practice.id,
            page_slug="test-booking",
            page_title="Test Booking",
            status=BookingPageStatus.ACTIVE,
        )
        db_session.add(page)
        await db_session.commit()

        response = await client.get("/api/v1/booking/pages/", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["count"] >= 1
        assert any(p["page_slug"] == "test-booking" for p in data["pages"])

    async def test_get_booking_page(self, client: AsyncClient, auth_headers, db_session, test_practice):
        page = BookingPage(
            practice_id=test_practice.id,
            page_slug="get-page",
            page_title="Get Page",
            status=BookingPageStatus.ACTIVE,
        )
        db_session.add(page)
        await db_session.commit()

        response = await client.get(f"/api/v1/booking/pages/{page.id}", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == str(page.id)
        assert data["page_slug"] == "get-page"

    async def test_get_booking_page_not_found(self, client: AsyncClient, auth_headers):
        import uuid
        response = await client.get(f"/api/v1/booking/pages/{uuid.uuid4()}", headers=auth_headers)
        assert response.status_code == 404

    async def test_create_booking_page(self, client: AsyncClient, auth_headers):
        response = await client.post(
            "/api/v1/booking/pages/",
            headers=auth_headers,
            json={
                "page_slug": "new-booking-page",
                "page_title": "New Booking Page",
                "welcome_message": "Welcome!",
                "primary_color": "#FF0000",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["page_slug"] == "new-booking-page"
        assert data["page_title"] == "New Booking Page"

    async def test_create_booking_page_duplicate_slug(self, client: AsyncClient, auth_headers, db_session, test_practice):
        page = BookingPage(
            practice_id=test_practice.id,
            page_slug="dup-slug",
            page_title="Dup Slug",
            status=BookingPageStatus.ACTIVE,
        )
        db_session.add(page)
        await db_session.commit()

        response = await client.post(
            "/api/v1/booking/pages/",
            headers=auth_headers,
            json={
                "page_slug": "dup-slug",
                "page_title": "Another Page",
            },
        )
        assert response.status_code == 409

    async def test_update_booking_page(self, client: AsyncClient, auth_headers, db_session, test_practice):
        page = BookingPage(
            practice_id=test_practice.id,
            page_slug="update-page",
            page_title="Update Page",
            status=BookingPageStatus.ACTIVE,
        )
        db_session.add(page)
        await db_session.commit()

        response = await client.put(
            f"/api/v1/booking/pages/{page.id}",
            headers=auth_headers,
            json={"page_title": "Updated Title"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["page_title"] == "Updated Title"

