"""
Common Response Schemas
Standardized API response structures
"""

from typing import Generic, TypeVar, Optional, List
from pydantic import BaseModel

T = TypeVar("T")


class BaseSchema(BaseModel):
    """Base schema for all API schemas"""
    pass


class APIResponse(BaseModel, Generic[T]):
    """Standardized API response envelope"""
    success: bool = True
    data: Optional[T] = None
    message: Optional[str] = None
    error: Optional[str] = None


class PaginatedResponse(BaseModel, Generic[T]):
    """Paginated list response"""
    success: bool = True
    items: List[T]
    total: int
    page: int
    limit: int
    pages: int

    @classmethod
    def create(cls, items: List[T], total: int, page: int, limit: int) -> "PaginatedResponse[T]":
        """Create a paginated response with calculated page count"""
        import math
        pages = math.ceil(total / limit) if limit > 0 else 0
        return cls(
            items=items,
            total=total,
            page=page,
            limit=limit,
            pages=pages
        )


class ErrorResponse(BaseModel):
    """Error response"""
    success: bool = False
    error: str
    detail: Optional[str] = None