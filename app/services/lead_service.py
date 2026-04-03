"""
Lead Service
Business logic for lead CRUD operations, search, and export
"""

from typing import List, Optional, Dict, Any, Tuple
from uuid import UUID
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_
import csv
import json
from io import StringIO, BytesIO

from app.models.lead import Lead, LeadStatus, LeadSource, LeadQuality
from app.models.campaign import Campaign
from app.schemas.lead import LeadCreate, LeadUpdate, LeadSearchParams
from app.db.repositories.lead_repository import LeadRepository
from app.core.logging import get_logger
from app.guardrails.input_validator import InputValidator
from app.guardrails.pii_detector import mask_pii
from app.core.config import settings

logger = get_logger(__name__)


class LeadService:
    """Service for lead business logic"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repository = LeadRepository(db)
        self.validator = InputValidator()
    
    async def get_leads(
        self,
        filters: Dict[str, Any],
        offset: int = 0,
        limit: int = 20,
        sort_by: Optional[str] = None,
        sort_order: str = "desc"
    ) -> Tuple[List[Lead], int]:
        """
        Get leads with filters and pagination
        """
        try:
            leads, total = await self.repository.get_all(
                filters=filters,
                offset=offset,
                limit=limit,
                sort_by=sort_by,
                sort_order=sort_order
            )
            return leads, total
        except Exception as e:
            logger.error(f"Error fetching leads: {e}")
            raise
    
    async def get_lead_by_id(self, lead_id: UUID) -> Optional[Lead]:
        """Get lead by ID"""
        return await self.repository.get_by_id(lead_id)
    
    async def get_lead_by_email(self, email: str) -> Optional[Lead]:
        """Get lead by email"""
        return await self.repository.get_by_email(email)
    
    async def create_lead(
        self,
        lead_data: Dict[str, Any],
        user_id: Optional[UUID] = None
    ) -> Lead:
        """
        Create a new lead
        """
        # Validate input
        is_valid, error = self.validator.validate_email(lead_data.get("email", ""))
        if not is_valid:
            raise ValueError(f"Invalid email: {error}")
        
        if lead_data.get("linkedin_url"):
            is_valid, error = self.validator.validate_url(lead_data["linkedin_url"])
            if not is_valid:
                raise ValueError(f"Invalid LinkedIn URL: {error}")
        
        # Generate full name
        first_name = lead_data.get("first_name", "")
        last_name = lead_data.get("last_name", "")
        if first_name or last_name:
            lead_data["full_name"] = f"{first_name} {last_name}".strip()
        
        # Set defaults
        lead_data["status"] = LeadStatus.NEW
        lead_data["score"] = 0
        lead_data["quality"] = LeadQuality.UNQUALIFIED
        
        # Create lead
        lead = await self.repository.create(lead_data, user_id)
        logger.info(f"Lead created: {lead.email}")
        
        return lead
    
    async def update_lead(
        self,
        lead_id: UUID,
        update_data: Dict[str, Any],
        user_id: Optional[UUID] = None
    ) -> Optional[Lead]:
        """
        Update an existing lead
        """
        lead = await self.repository.get_by_id(lead_id)
        if not lead:
            return None
        
        # Update full name if first/last name changed
        if "first_name" in update_data or "last_name" in update_data:
            first = update_data.get("first_name", lead.first_name)
            last = update_data.get("last_name", lead.last_name)
            update_data["full_name"] = f"{first} {last}".strip() if first or last else None
        
        # Update quality based on score if score changed
        if "score" in update_data:
            score = update_data["score"]
            if score >= 80:
                update_data["quality"] = LeadQuality.HOT
            elif score >= 60:
                update_data["quality"] = LeadQuality.WARM
            elif score >= 40:
                update_data["quality"] = LeadQuality.COLD
            else:
                update_data["quality"] = LeadQuality.UNQUALIFIED
        
        lead = await self.repository.update(lead_id, update_data, user_id)
        logger.info(f"Lead updated: {lead.email if lead else lead_id}")
        
        return lead
    
    async def delete_lead(self, lead_id: UUID) -> bool:
        """Soft delete a lead"""
        return await self.repository.soft_delete(lead_id)
    
    async def bulk_create_leads(
        self,
        leads_data: List[Dict[str, Any]],
        user_id: Optional[UUID] = None
    ) -> Dict[str, Any]:
        """
        Create multiple leads in bulk
        Returns stats about operation
        """
        successful = 0
        failed = 0
        errors = []
        
        for idx, lead_data in enumerate(leads_data):
            try:
                # Validate email
                is_valid, error = self.validator.validate_email(lead_data.get("email", ""))
                if not is_valid:
                    errors.append({"index": idx, "reason": f"Invalid email: {error}"})
                    failed += 1
                    continue
                
                # Check for duplicate
                existing = await self.repository.get_by_email(lead_data["email"])
                if existing:
                    errors.append({"index": idx, "reason": "Email already exists"})
                    failed += 1
                    continue
                
                # Create lead
                await self.create_lead(lead_data, user_id)
                successful += 1
                
            except Exception as e:
                errors.append({"index": idx, "reason": str(e)})
                failed += 1
        
        return {
            "successful": successful,
            "failed": failed,
            "errors": errors[:100]  # Limit errors
        }
    
    async def search_leads(
        self,
        search_params: Dict[str, Any],
        offset: int = 0,
        limit: int = 20
    ) -> Tuple[List[Lead], int]:
        """
        Advanced search with multiple criteria
        """
        query = select(Lead).where(Lead.is_deleted == False)
        
        # Apply filters
        if search_params.get("query"):
            query = query.where(
                or_(
                    Lead.full_name.ilike(f"%{search_params['query']}%"),
                    Lead.email.ilike(f"%{search_params['query']}%"),
                    Lead.company_name.ilike(f"%{search_params['query']}%"),
                    Lead.job_title.ilike(f"%{search_params['query']}%")
                )
            )
        
        if search_params.get("email"):
            query = query.where(Lead.email.ilike(f"%{search_params['email']}%"))
        
        if search_params.get("company_name"):
            query = query.where(Lead.company_name.ilike(f"%{search_params['company_name']}%"))
        
        if search_params.get("status"):
            query = query.where(Lead.status == search_params["status"])
        
        if search_params.get("source"):
            query = query.where(Lead.source == search_params["source"])
        
        if search_params.get("quality"):
            query = query.where(Lead.quality == search_params["quality"])
        
        if search_params.get("min_score"):
            query = query.where(Lead.score >= search_params["min_score"])
        
        if search_params.get("max_score"):
            query = query.where(Lead.score <= search_params["max_score"])
        
        if search_params.get("campaign_id"):
            query = query.where(Lead.campaign_id == search_params["campaign_id"])
        
        if search_params.get("created_after"):
            query = query.where(Lead.created_at >= search_params["created_after"])
        
        if search_params.get("created_before"):
            query = query.where(Lead.created_at <= search_params["created_before"])
        
        # Get total count
        count_query = select(func.count()).select_from(query.subquery())
        total = await self.db.execute(count_query)
        total = total.scalar_one()
        
        # Apply pagination
        query = query.offset(offset).limit(limit)
        
        # Execute query
        result = await self.db.execute(query)
        leads = result.scalars().all()
        
        return leads, total
    
    async def export_leads(
        self,
        format: str,
        filters: Optional[Dict[str, Any]] = None,
        fields: Optional[List[str]] = None,
        include_metadata: bool = False,
        user_email: Optional[str] = None
    ) -> str:
        """
        Export leads to CSV, JSON, or Excel
        Returns download URL
        """
        # Fetch leads
        leads, total = await self.search_leads(filters or {}, offset=0, limit=settings.export_max_rows)
        
        # Define export fields
        default_fields = [
            "email", "first_name", "last_name", "full_name", "company_name",
            "job_title", "location", "score", "quality", "status", "source"
        ]
        export_fields = fields or default_fields
        
        # Generate export based on format
        if format == "csv":
            content = await self._export_to_csv(leads, export_fields)
            extension = "csv"
            mime_type = "text/csv"
        elif format == "json":
            content = await self._export_to_json(leads, export_fields, include_metadata)
            extension = "json"
            mime_type = "application/json"
        elif format == "excel":
            content = await self._export_to_excel(leads, export_fields)
            extension = "xlsx"
            mime_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        else:
            raise ValueError(f"Unsupported export format: {format}")
        
        # Save to temp file (in production, save to S3)
        filename = f"leads_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.{extension}"
        filepath = f"{settings.export_temp_dir}/{filename}"
        
        import os
        os.makedirs(settings.export_temp_dir, exist_ok=True)
        
        with open(filepath, "wb") as f:
            f.write(content)
        
        # In production, return S3 URL instead
        download_url = f"/exports/{filename}"
        
        logger.info(f"Exported {len(leads)} leads to {format}: {filename}")
        
        return download_url
    
    async def _export_to_csv(self, leads: List[Lead], fields: List[str]) -> bytes:
        """Export leads to CSV"""
        output = StringIO()
        writer = csv.DictWriter(output, fieldnames=fields)
        writer.writeheader()
        
        for lead in leads:
            row = {}
            for field in fields:
                value = getattr(lead, field, None)
                # Mask PII in CSV
                if field == "email":
                    value = mask_pii(value)
                row[field] = value
            writer.writerow(row)
        
        return output.getvalue().encode('utf-8')
    
    async def _export_to_json(self, leads: List[Lead], fields: List[str], include_metadata: bool) -> bytes:
        """Export leads to JSON"""
        data = []
        for lead in leads:
            lead_dict = {}
            for field in fields:
                value = getattr(lead, field, None)
                if field == "email":
                    value = mask_pii(value)
                lead_dict[field] = value
            
            if include_metadata:
                lead_dict["metadata"] = lead.metadata
                lead_dict["enriched_data"] = lead.enriched_data
            
            data.append(lead_dict)
        
        return json.dumps(data, default=str, indent=2).encode('utf-8')
    
    async def _export_to_excel(self, leads: List[Lead], fields: List[str]) -> bytes:
        """Export leads to Excel"""
        try:
            import pandas as pd
            from io import BytesIO
            
            data = []
            for lead in leads:
                row = {}
                for field in fields:
                    value = getattr(lead, field, None)
                    if field == "email":
                        value = mask_pii(value)
                    row[field] = value
                data.append(row)
            
            df = pd.DataFrame(data)
            output = BytesIO()
            
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                df.to_excel(writer, sheet_name='Leads', index=False)
            
            return output.getvalue()
        except ImportError:
            logger.warning("pandas not installed, falling back to CSV")
            return await self._export_to_csv(leads, fields)
    
    async def qualify_lead(self, lead_id: UUID, use_ai: bool = True) -> Optional[Dict[str, Any]]:
        """
        Qualify a lead using AI or rules
        """
        lead = await self.repository.get_by_id(lead_id)
        if not lead:
            return None
        
        if use_ai:
            # Use AI for qualification
            from app.services.enrichment_service import EnrichmentService
            enrichment_service = EnrichmentService()
            result = await enrichment_service.qualify_lead(lead)
        else:
            # Use rule-based qualification
            result = self._rule_based_qualification(lead)
        
        # Update lead status based on qualification
        if result.get("is_qualified", False):
            lead.status = LeadStatus.QUALIFIED
        else:
            lead.status = LeadStatus.REJECTED
        
        await self.repository.update(lead_id, {
            "status": lead.status,
            "metadata": {**lead.metadata, "qualification": result}
        })
        
        return result
    
    def _rule_based_qualification(self, lead: Lead) -> Dict[str, Any]:
        """Rule-based qualification logic"""
        score = lead.score or 0
        has_email = bool(lead.email)
        has_company = bool(lead.company_name)
        has_job_title = bool(lead.job_title)
        
        is_qualified = (
            score >= 60 and
            has_email and
            (has_company or has_job_title)
        )
        
        return {
            "is_qualified": is_qualified,
            "score": score,
            "reasons": [
                f"Score: {score} {'>= 60' if score >= 60 else '< 60'}",
                f"Email: {'Yes' if has_email else 'No'}",
                f"Company: {'Yes' if has_company else 'No'}",
                f"Job Title: {'Yes' if has_job_title else 'No'}"
            ]
        }
    
    async def get_lead_stats(self, campaign_id: Optional[UUID] = None) -> Dict[str, Any]:
        """Get lead statistics"""
        query = select(
            func.count(Lead.id).label("total"),
            func.avg(Lead.score).label("avg_score"),
            func.count(Lead.id).filter(Lead.status == LeadStatus.QUALIFIED).label("qualified"),
            func.count(Lead.id).filter(Lead.status == LeadStatus.CONTACTED).label("contacted"),
            func.count(Lead.id).filter(Lead.status == LeadStatus.CONVERTED).label("converted")
        )
        
        if campaign_id:
            query = query.where(Lead.campaign_id == campaign_id)
        
        result = await self.db.execute(query)
        stats = result.one()
        
        return {
            "total_leads": stats.total,
            "average_score": round(stats.avg_score or 0, 2),
            "qualified_leads": stats.qualified,
            "contacted_leads": stats.contacted,
            "converted_leads": stats.converted,
            "conversion_rate": round((stats.converted / stats.total * 100) if stats.total > 0 else 0, 2)
        }
    
    async def find_duplicate_leads(
        self,
        lead_id: UUID,
        similarity_threshold: float = 0.8
    ) -> List[Dict[str, Any]]:
        """
        Find duplicate leads using vector similarity
        """
        lead = await self.repository.get_by_id(lead_id)
        if not lead:
            return []
        
        # Use vector store for similarity search
        from app.vector_store.similarity_search import find_similar_leads
        
        similar_leads = await find_similar_leads(
            lead_email=lead.email,
            threshold=similarity_threshold,
            limit=10
        )
        
        return similar_leads