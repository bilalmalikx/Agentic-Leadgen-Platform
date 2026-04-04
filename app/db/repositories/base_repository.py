"""
Base Repository Pattern
Abstract base class for all repositories with common CRUD operations
"""

from typing import TypeVar, Generic, Type, List, Optional, Dict, Any, Tuple
from uuid import UUID
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete, func

from app.models.base import BaseModel

# Generic type for model
ModelType = TypeVar("ModelType", bound=BaseModel)


class BaseRepository(Generic[ModelType]):
    """
    Base repository with common CRUD operations
    All other repositories inherit from this
    """
    
    def __init__(self, db: AsyncSession, model: Type[ModelType]):
        self.db = db
        self.model = model
    
    async def create(self, data: Dict[str, Any], user_id: Optional[UUID] = None) -> ModelType:
        """
        Create a new record
        """
        # Add audit fields if available
        if user_id and hasattr(self.model, 'created_by'):
            data['created_by'] = user_id
        
        instance = self.model(**data)
        self.db.add(instance)
        await self.db.commit()
        await self.db.refresh(instance)
        return instance
    
    async def get_by_id(self, id: UUID) -> Optional[ModelType]:
        """
        Get record by ID
        """
        query = select(self.model).where(
            self.model.id == id,
            self.model.is_deleted == False if hasattr(self.model, 'is_deleted') else True
        )
        result = await self.db.execute(query)
        return result.scalar_one_or_none()
    
    async def get_all(
        self,
        filters: Optional[Dict[str, Any]] = None,
        offset: int = 0,
        limit: int = 100,
        sort_by: Optional[str] = None,
        sort_order: str = "desc"
    ) -> Tuple[List[ModelType], int]:
        """
        Get all records with pagination and filtering
        """
        # Build query
        query = select(self.model)
        
        # Apply soft delete filter
        if hasattr(self.model, 'is_deleted'):
            query = query.where(self.model.is_deleted == False)
        
        # Apply filters
        if filters:
            for key, value in filters.items():
                if hasattr(self.model, key) and value is not None:
                    if isinstance(value, str):
                        query = query.where(getattr(self.model, key).ilike(f"%{value}%"))
                    else:
                        query = query.where(getattr(self.model, key) == value)
        
        # Get total count
        count_query = select(func.count()).select_from(query.subquery())
        total = await self.db.execute(count_query)
        total = total.scalar_one()
        
        # Apply sorting
        if sort_by and hasattr(self.model, sort_by):
            sort_column = getattr(self.model, sort_by)
            if sort_order == "desc":
                query = query.order_by(sort_column.desc())
            else:
                query = query.order_by(sort_column.asc())
        else:
            query = query.order_by(self.model.created_at.desc())
        
        # Apply pagination
        query = query.offset(offset).limit(limit)
        
        # Execute query
        result = await self.db.execute(query)
        items = result.scalars().all()
        
        return items, total
    
    async def update(
        self,
        id: UUID,
        data: Dict[str, Any],
        user_id: Optional[UUID] = None
    ) -> Optional[ModelType]:
        """
        Update a record
        """
        # Add audit fields
        data['updated_at'] = datetime.utcnow()
        if user_id and hasattr(self.model, 'updated_by'):
            data['updated_by'] = user_id
        
        query = update(self.model).where(
            self.model.id == id,
            self.model.is_deleted == False if hasattr(self.model, 'is_deleted') else True
        ).values(**data).returning(self.model)
        
        result = await self.db.execute(query)
        await self.db.commit()
        
        updated = result.scalar_one_or_none()
        return updated
    
    async def delete(self, id: UUID, hard_delete: bool = False) -> bool:
        """
        Delete a record (soft delete by default)
        """
        if hard_delete:
            # Hard delete
            query = delete(self.model).where(self.model.id == id)
            result = await self.db.execute(query)
        else:
            # Soft delete
            if hasattr(self.model, 'is_deleted') and hasattr(self.model, 'deleted_at'):
                query = update(self.model).where(
                    self.model.id == id
                ).values(
                    is_deleted=True,
                    deleted_at=datetime.utcnow()
                )
                result = await self.db.execute(query)
            else:
                # If model doesn't support soft delete, hard delete
                query = delete(self.model).where(self.model.id == id)
                result = await self.db.execute(query)
        
        await self.db.commit()
        return result.rowcount > 0
    
    async def soft_delete(self, id: UUID) -> bool:
        """
        Soft delete a record
        """
        return await self.delete(id, hard_delete=False)
    
    async def exists(self, **filters) -> bool:
        """
        Check if a record exists with given filters
        """
        query = select(self.model)
        
        for key, value in filters.items():
            if hasattr(self.model, key):
                query = query.where(getattr(self.model, key) == value)
        
        if hasattr(self.model, 'is_deleted'):
            query = query.where(self.model.is_deleted == False)
        
        query = query.limit(1)
        result = await self.db.execute(query)
        return result.scalar_one_or_none() is not None
    
    async def count(self, filters: Optional[Dict[str, Any]] = None) -> int:
        """
        Count records with optional filters
        """
        query = select(func.count()).select_from(self.model)
        
        if hasattr(self.model, 'is_deleted'):
            query = query.where(self.model.is_deleted == False)
        
        if filters:
            for key, value in filters.items():
                if hasattr(self.model, key) and value is not None:
                    query = query.where(getattr(self.model, key) == value)
        
        result = await self.db.execute(query)
        return result.scalar_one()
    
    async def bulk_create(self, items: List[Dict[str, Any]]) -> List[ModelType]:
        """
        Bulk create multiple records
        """
        instances = [self.model(**item) for item in items]
        self.db.add_all(instances)
        await self.db.commit()
        
        for instance in instances:
            await self.db.refresh(instance)
        
        return instances
    
    async def bulk_update(
        self,
        updates: List[Tuple[UUID, Dict[str, Any]]]
    ) -> int:
        """
        Bulk update multiple records
        """
        updated_count = 0
        
        for id, data in updates:
            result = await self.update(id, data)
            if result:
                updated_count += 1
        
        return updated_count