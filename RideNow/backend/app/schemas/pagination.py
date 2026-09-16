from typing import Generic, TypeVar, List
from pydantic import BaseModel

T = TypeVar("T")


class PaginatedResponse(BaseModel, Generic[T]):
    """Generic paginated response used by ride history, etc."""
    items: List[T]
    page: int
    page_size: int
    total: int
    total_pages: int
