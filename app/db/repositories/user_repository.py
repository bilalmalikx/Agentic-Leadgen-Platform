"""
User Repository
Database operations for User and API Key models
"""

from typing import List, Optional, Dict, Any, Tuple
from uuid import UUID
from datetime import datetime, timedelta
from sqlalchemy import select, func, and_, or_
from sqlalchemy.orm import selectinload

from app.db.repositories.base_repository import BaseRepository
from app.models.user import User, UserStatus, UserRole, APIKey
from app.core.security import get_password_hash, hash_api_key
from app.core.logging import get_logger

logger = get_logger(__name__)


class UserRepository(BaseRepository[User]):
    """Repository for User model operations"""
    
    def __init__(self, db):
        super().__init__(db, User)
    
    async def get_by_email(self, email: str) -> Optional[User]:
        """
        Get user by email address
        """
        query = select(self.model).where(
            self.model.email.ilike(email),
            self.model.is_deleted == False
        )
        result = await self.db.execute(query)
        return result.scalar_one_or_none()
    
    async def get_by_api_key(self, api_key: str) -> Optional[User]:
        """
        Get user by API key
        """
        from app.core.security import hash_api_key
        
        key_hash = hash_api_key(api_key)
        
        query = select(APIKey).where(
            APIKey.key_hash == key_hash,
            APIKey.is_active == True,
            APIKey.expires_at > datetime.utcnow() if APIKey.expires_at is not None else True
        )
        
        result = await self.db.execute(query)
        api_key_obj = result.scalar_one_or_none()
        
        if api_key_obj:
            # Update last used timestamp
            api_key_obj.last_used_at = datetime.utcnow()
            await self.db.commit()
            
            # Get user
            return await self.get_by_id(api_key_obj.user_id)
        
        return None
    
    async def create_user(
        self,
        email: str,
        password: str,
        full_name: Optional[str] = None,
        company: Optional[str] = None,
        role: UserRole = UserRole.USER
    ) -> User:
        """
        Create a new user with hashed password
        """
        password_hash = get_password_hash(password)
        
        user_data = {
            "email": email,
            "password_hash": password_hash,
            "full_name": full_name,
            "company": company,
            "role": role,
            "status": UserStatus.ACTIVE
        }
        
        return await self.create(user_data)
    
    async def authenticate(self, email: str, password: str) -> Optional[User]:
        """
        Authenticate user by email and password
        """
        from app.core.security import verify_password
        
        user = await self.get_by_email(email)
        
        if not user:
            return None
        
        if not verify_password(password, user.password_hash):
            return None
        
        if user.status != UserStatus.ACTIVE:
            return None
        
        # Update last login
        user.last_login_at = datetime.utcnow()
        await self.db.commit()
        await self.db.refresh(user)
        
        return user
    
    async def update_password(self, user_id: UUID, new_password: str) -> bool:
        """
        Update user password
        """
        from app.core.security import get_password_hash
        
        password_hash = get_password_hash(new_password)
        user = await self.update(user_id, {"password_hash": password_hash})
        
        return user is not None
    
    async def consume_quota(self, user_id: UUID, leads_count: int = 1) -> bool:
        """
        Consume user quota for lead generation
        """
        user = await self.get_by_id(user_id)
        
        if not user:
            return False
        
        # Check if quota needs reset (new month)
        if user.quota_reset_at and user.quota_reset_at.month != datetime.utcnow().month:
            user.leads_generated_this_month = 0
            user.api_calls_this_month = 0
            user.quota_reset_at = datetime.utcnow()
        
        # Check if enough quota
        if user.leads_generated_this_month + leads_count > user.monthly_lead_quota:
            return False
        
        # Consume quota
        user.leads_generated_this_month += leads_count
        await self.db.commit()
        
        return True
    
    async def get_api_keys(self, user_id: UUID) -> List[APIKey]:
        """
        Get all API keys for a user
        """
        query = select(APIKey).where(
            APIKey.user_id == user_id,
            APIKey.is_deleted == False
        ).order_by(APIKey.created_at.desc())
        
        result = await self.db.execute(query)
        return result.scalars().all()
    
    async def create_api_key(
        self,
        user_id: UUID,
        name: str,
        expires_in_days: int = 365,
        permissions: List[str] = None,
        allowed_ips: List[str] = None
    ) -> Tuple[APIKey, str]:
        """
        Create a new API key for user
        Returns (api_key_object, plain_key)
        """
        from app.core.security import generate_api_key, hash_api_key
        
        # Generate key
        plain_key = generate_api_key()
        key_hash = hash_api_key(plain_key)
        key_prefix = plain_key[:10]
        
        # Calculate expiry
        expires_at = datetime.utcnow() + timedelta(days=expires_in_days)
        
        # Create API key record
        api_key = APIKey(
            user_id=user_id,
            key_hash=key_hash,
            key_prefix=key_prefix,
            name=name,
            permissions=permissions or ["read"],
            allowed_ips=allowed_ips,
            expires_at=expires_at,
            is_active=True
        )
        
        self.db.add(api_key)
        await self.db.commit()
        await self.db.refresh(api_key)
        
        logger.info(f"API key created for user {user_id}: {key_prefix}...")
        
        return api_key, plain_key
    
    async def revoke_api_key(self, api_key_id: UUID) -> bool:
        """
        Revoke an API key
        """
        query = select(APIKey).where(APIKey.id == api_key_id)
        result = await self.db.execute(query)
        api_key = result.scalar_one_or_none()
        
        if not api_key:
            return False
        
        api_key.is_active = False
        await self.db.commit()
        
        logger.info(f"API key {api_key.key_prefix}... revoked")
        return True
    
    async def update_user_quota(self, user_id: UUID, monthly_quota: int) -> Optional[User]:
        """
        Update user's monthly lead quota
        """
        return await self.update(user_id, {"monthly_lead_quota": monthly_quota})
    
    async def get_users_by_role(self, role: UserRole) -> List[User]:
        """
        Get all users with specific role
        """
        query = select(self.model).where(
            self.model.role == role,
            self.model.status == UserStatus.ACTIVE,
            self.model.is_deleted == False
        )
        
        result = await self.db.execute(query)
        return result.scalars().all()
    
    async def get_quota_exceeded_users(self) -> List[User]:
        """
        Get users who have exceeded their monthly quota
        """
        query = select(self.model).where(
            self.model.leads_generated_this_month >= self.model.monthly_lead_quota,
            self.model.status == UserStatus.ACTIVE,
            self.model.is_deleted == False
        )
        
        result = await self.db.execute(query)
        return result.scalars().all()
    
    async def reset_all_quotas(self) -> int:
        """
        Reset monthly quotas for all users (run at start of month)
        """
        query = select(self.model).where(
            self.model.status == UserStatus.ACTIVE,
            self.model.is_deleted == False
        )
        
        result = await self.db.execute(query)
        users = result.scalars().all()
        
        for user in users:
            user.leads_generated_this_month = 0
            user.api_calls_this_month = 0
            user.quota_reset_at = datetime.utcnow()
        
        await self.db.commit()
        
        logger.info(f"Reset quotas for {len(users)} users")
        return len(users)
    
    async def get_user_stats(self, user_id: UUID) -> Dict[str, Any]:
        """
        Get user statistics
        """
        user = await self.get_by_id(user_id)
        
        if not user:
            return {}
        
        # Get campaign stats
        from app.db.repositories.campaign_repository import CampaignRepository
        campaign_repo = CampaignRepository(self.db)
        campaign_stats = await campaign_repo.get_campaign_stats(user_id)
        
        # Get API key count
        api_keys = await self.get_api_keys(user_id)
        
        return {
            "user": {
                "id": str(user.id),
                "email": user.email,
                "role": user.role.value,
                "status": user.status.value
            },
            "quota": {
                "monthly_quota": user.monthly_lead_quota,
                "used_this_month": user.leads_generated_this_month,
                "remaining": max(0, user.monthly_lead_quota - user.leads_generated_this_month),
                "api_calls_this_month": user.api_calls_this_month
            },
            "campaigns": campaign_stats,
            "api_keys_count": len(api_keys),
            "joined_at": user.created_at.isoformat() if user.created_at else None,
            "last_login": user.last_login_at.isoformat() if user.last_login_at else None
        }