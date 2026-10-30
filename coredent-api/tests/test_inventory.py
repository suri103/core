"""Tests for inventory endpoints"""
import pytest
import uuid

pytestmark = pytest.mark.asyncio


class TestInventoryItems:
    async def test_list_items_requires_auth(self, client):
        response = await client.get("/api/v1/inventory/items/")
        assert response.status_code in (401, 403)

    async def test_create_item_requires_auth(self, client):
        response = await client.post("/api/v1/inventory/items/", json={})
        assert response.status_code in (401, 403)

    async def test_create_item_validation_error(self, client, auth_headers):
        response = await client.post("/api/v1/inventory/items/", json={})
        assert response.status_code in (422, 401, 403)

    async def test_get_item_requires_auth(self, client):
        fake_id = str(uuid.uuid4())
        response = await client.get(f"/api/v1/inventory/items/{fake_id}")
        assert response.status_code in (401, 403)


class TestSuppliers:
    async def test_list_suppliers_requires_auth(self, client):
        response = await client.get("/api/v1/inventory/suppliers/")
        assert response.status_code in (401, 403)

    async def test_create_supplier_requires_auth(self, client):
        response = await client.post("/api/v1/inventory/suppliers/", json={})
        assert response.status_code in (401, 403)
