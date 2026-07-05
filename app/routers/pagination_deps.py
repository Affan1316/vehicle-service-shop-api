from fastapi import Query
from fastapi_pagination import LimitOffsetParams

class PaginationParams(LimitOffsetParams):
    """FastAPI query parameter dependency class to validate and standardise pagination input, compatible with fastapi-pagination."""
    limit: int = Query(20, ge=1, le=100, description="Number of records to return (1-100)")
    offset: int = Query(0, ge=0, description="Offset index to start returning records")
