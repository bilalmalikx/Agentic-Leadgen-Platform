"""
Pagination
Helper functions for paginated responses
"""

from typing import List, TypeVar, Generic, Optional, Dict, Any
from math import ceil

T = TypeVar('T')


class PaginationHelper:
    """Helper class for pagination"""
    
    def __init__(self, page: int = 1, per_page: int = 20, max_per_page: int = 100):
        self.page = max(1, page)
        self.per_page = min(max_per_page, max(1, per_page))
        self.max_per_page = max_per_page
    
    @property
    def offset(self) -> int:
        """Calculate SQL OFFSET"""
        return (self.page - 1) * self.per_page
    
    @property
    def limit(self) -> int:
        """Calculate SQL LIMIT"""
        return self.per_page
    
    def get_metadata(self, total: int) -> Dict[str, Any]:
        """Generate pagination metadata"""
        total_pages = ceil(total / self.per_page) if total > 0 else 1
        
        return {
            "page": self.page,
            "per_page": self.per_page,
            "total": total,
            "total_pages": total_pages,
            "has_next": self.page < total_pages,
            "has_prev": self.page > 1,
            "next_page": self.page + 1 if self.page < total_pages else None,
            "prev_page": self.page - 1 if self.page > 1 else None
        }
    
    def paginate(self, items: List[T], total: int) -> Dict[str, Any]:
        """Paginate a list of items"""
        start = self.offset
        end = start + self.per_page
        
        return {
            "items": items[start:end],
            "metadata": self.get_metadata(total)
        }


class CursorPagination:
    """
    Cursor-based pagination for infinite scrolling
    More efficient for large datasets
    """
    
    def __init__(self, cursor: Optional[str] = None, limit: int = 20, max_limit: int = 100):
        self.cursor = cursor
        self.limit = min(max_limit, max(1, limit))
        self.max_limit = max_limit
    
    def get_metadata(self, has_more: bool, next_cursor: Optional[str] = None) -> Dict[str, Any]:
        """Generate cursor pagination metadata"""
        return {
            "limit": self.limit,
            "has_more": has_more,
            "next_cursor": next_cursor
        }
    
    @staticmethod
    def encode_cursor(value: Any) -> str:
        """Encode cursor value to string"""
        import base64
        return base64.b64encode(str(value).encode()).decode()
    
    @staticmethod
    def decode_cursor(cursor: str) -> Any:
        """Decode cursor string to value"""
        import base64
        try:
            decoded = base64.b64decode(cursor.encode()).decode()
            return decoded
        except:
            return None


def paginate_list(items: List[T], page: int = 1, per_page: int = 20) -> Dict[str, Any]:
    """Simple pagination for lists"""
    helper = PaginationHelper(page=page, per_page=per_page)
    total = len(items)
    return helper.paginate(items, total)


def get_page_from_params(page: int = 1, limit: int = 20) -> PaginationHelper:
    """Create pagination helper from query parameters"""
    return PaginationHelper(page=page, per_page=limit)