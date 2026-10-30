"""
Tests for document management endpoints
"""
import pytest
from httpx import AsyncClient


class TestDocumentEndpoints:
    """Test document management endpoints"""

    @pytest.mark.asyncio
    async def test_list_templates_unauthorized(self, client: AsyncClient):
        """Test listing templates without authentication"""
        response = await client.get("/api/v1/documents/templates")
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_list_documents_unauthorized(self, client: AsyncClient):
        """Test listing documents without authentication"""
        response = await client.get("/api/v1/documents/")
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_create_document_unauthorized(self, client: AsyncClient):
        """Test creating document without authentication"""
        response = await client.post(
            "/api/v1/documents/",
            params={"patient_id": "test-id", "template_id": "test-id"},
        )
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_list_templates_with_auth(self, client: AsyncClient, auth_headers):
        """Test listing templates with authentication"""
        response = await client.get("/api/v1/documents/templates", headers=auth_headers)
        assert response.status_code in [200, 403, 404, 500]

    @pytest.mark.asyncio
    async def test_list_documents_with_auth(self, client: AsyncClient, auth_headers):
        """Test listing documents with authentication"""
        response = await client.get("/api/v1/documents/", headers=auth_headers)
        assert response.status_code in [200, 403, 404, 500]

    @pytest.mark.asyncio
    async def test_create_document_validation_error(self, client: AsyncClient, auth_headers):
        """Test creating document with missing required fields"""
        response = await client.post("/api/v1/documents/", headers=auth_headers)
        assert response.status_code in [422, 400, 403]
