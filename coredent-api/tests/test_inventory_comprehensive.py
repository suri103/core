"""
Comprehensive inventory endpoint tests.
"""
import pytest
from httpx import AsyncClient

from app.models.inventory import InventoryItem, InventoryCategory

pytestmark = pytest.mark.asyncio


class TestInventoryItemCRUD:
    """Inventory item CRUD tests."""

    async def test_list_inventory_items(self, client: AsyncClient, auth_headers, db_session, test_practice):
        item = InventoryItem(
            practice_id=test_practice.id,
            name="Dental Gloves",
            sku="GLV-001",
            category=InventoryCategory.SUPPLIES,
            current_quantity=100,
            minimum_quantity=20,
        )
        db_session.add(item)
        await db_session.commit()

        response = await client.get("/api/v1/inventory/items/", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["count"] >= 1
        assert any(i["name"] == "Dental Gloves" for i in data["items"])

    async def test_list_inventory_items_search(self, client: AsyncClient, auth_headers, db_session, test_practice):
        item = InventoryItem(
            practice_id=test_practice.id,
            name="Face Masks",
            sku="MSK-002",
            category=InventoryCategory.SUPPLIES,
            current_quantity=50,
        )
        db_session.add(item)
        await db_session.commit()

        response = await client.get("/api/v1/inventory/items/?search=Face", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert all("Face" in i["name"] or "Face" in (i.get("sku") or "") for i in data["items"])

    async def test_get_inventory_item(self, client: AsyncClient, auth_headers, db_session, test_practice):
        item = InventoryItem(
            practice_id=test_practice.id,
            name="Curing Light",
            sku="CL-001",
            category=InventoryCategory.EQUIPMENT,
            current_quantity=2,
        )
        db_session.add(item)
        await db_session.commit()

        response = await client.get(f"/api/v1/inventory/items/{item.id}", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == str(item.id)
        assert data["name"] == "Curing Light"

    async def test_get_inventory_item_not_found(self, client: AsyncClient, auth_headers):
        import uuid
        response = await client.get(f"/api/v1/inventory/items/{uuid.uuid4()}", headers=auth_headers)
        assert response.status_code == 404

    async def test_create_inventory_item(self, client: AsyncClient, auth_headers):
        response = await client.post(
            "/api/v1/inventory/items/",
            headers=auth_headers,
            json={
                "name": "Composite Resin",
                "sku": "RES-001",
                "category": "supplies",
                "current_quantity": 30,
                "minimum_quantity": 5,
                "unit_cost": "45.00",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Composite Resin"
        assert data["sku"] == "RES-001"

    async def test_update_inventory_item(self, client: AsyncClient, auth_headers, db_session, test_practice):
        item = InventoryItem(
            practice_id=test_practice.id,
            name="Old Name",
            sku="OLD-001",
            current_quantity=10,
        )
        db_session.add(item)
        await db_session.commit()

        response = await client.put(
            f"/api/v1/inventory/items/{item.id}",
            headers=auth_headers,
            json={"name": "Updated Name", "current_quantity": 25},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Updated Name"
        assert data["current_quantity"] == 25

    async def test_delete_inventory_item(self, client: AsyncClient, auth_headers, db_session, test_practice):
        item = InventoryItem(
            practice_id=test_practice.id,
            name="To Delete",
            sku="DEL-001",
            current_quantity=1,
        )
        db_session.add(item)
        await db_session.commit()

        response = await client.delete(f"/api/v1/inventory/items/{item.id}", headers=auth_headers)
        assert response.status_code == 200
        assert "deleted" in response.json()["message"].lower()
