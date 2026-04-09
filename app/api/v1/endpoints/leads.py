"""
Lead Endpoints
CRUD operations, search, export, and bulk operations for leads
"""

from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks, status
from typing import List, Optional
from uuid import UUID

from app.api.dependencies import get_current_user, get_db_session, get_lead_service
from app.schemas.lead import (
    LeadCreate, LeadUpdate, LeadResponse, LeadDetailResponse,
    LeadSearchParams, LeadBulkCreate, LeadExportRequest, LeadScoreUpdate,
    LeadQualifyRequest, LeadStatusEnum
)
from app.schemas.common import (
    SuccessResponse, ErrorResponse, PaginatedResponse, PaginationParams,
    BulkOperationResponse, IDResponse
)
from app.services.lead_service import LeadService
from app.core.logging import get_logger
from app.guardrails.input_validator import InputValidator
from app.workers.lead_tasks import enrich_leads_task, score_leads_task
from app.core.database import get_session

router = APIRouter()
logger = get_logger(__name__)


@router.get("/", response_model=PaginatedResponse[LeadResponse])
async def get_leads(
    search: LeadSearchParams = Depends(),
    pagination: PaginationParams = Depends(),
    current_user: dict = Depends(get_current_user),
    lead_service: LeadService = Depends(get_lead_service)
):
    """
    Get list of leads with filtering and pagination
    """
    try:
        leads, total = await lead_service.get_leads(
            filters=search.dict(exclude_none=True),
            offset=pagination.offset(),
            limit=pagination.limit,
            sort_by=pagination.sort_by,
            sort_order=pagination.sort_order
        )
        
        return PaginatedResponse.create(
            items=leads,
            total=total,
            params=pagination
        )
    except Exception as e:
        logger.error(f"Error fetching leads: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/{lead_id}", response_model=LeadDetailResponse)
async def get_lead(
    lead_id: UUID,
    current_user: dict = Depends(get_current_user),
    lead_service: LeadService = Depends(get_lead_service)
):
    """
    Get lead by ID with full details
    """
    lead = await lead_service.get_lead_by_id(lead_id)
    
    if not lead:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Lead with ID {lead_id} not found"
        )
    
    return lead


@router.post("/", response_model=IDResponse, status_code=status.HTTP_201_CREATED)
async def create_lead(
    lead_data: LeadCreate,
    current_user: dict = Depends(get_current_user),
    lead_service: LeadService = Depends(get_lead_service)
):
    """
    Create a new lead manually
    """
    # Validate input
    validator = InputValidator()
    is_valid, error = validator.validate_email(lead_data.email)
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid email: {error}"
        )
    
    # Check for duplicate
    existing = await lead_service.get_lead_by_email(lead_data.email)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Lead with email {lead_data.email} already exists"
        )
    
    # Create lead
    lead = await lead_service.create_lead(
        lead_data=lead_data,
        user_id=current_user.get("user_id")
    )
    
    return IDResponse(id=lead.id, message="Lead created successfully")


@router.put("/{lead_id}", response_model=SuccessResponse)
async def update_lead(
    lead_id: UUID,
    lead_data: LeadUpdate,
    current_user: dict = Depends(get_current_user),
    lead_service: LeadService = Depends(get_lead_service)
):
    """
    Update an existing lead
    """
    updated = await lead_service.update_lead(
        lead_id=lead_id,
        update_data=lead_data.dict(exclude_none=True),
        user_id=current_user.get("user_id")
    )
    
    if not updated:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Lead with ID {lead_id} not found"
        )
    
    return SuccessResponse(message="Lead updated successfully")


@router.delete("/{lead_id}", response_model=SuccessResponse)
async def delete_lead(
    lead_id: UUID,
    current_user: dict = Depends(get_current_user),
    lead_service: LeadService = Depends(get_lead_service)
):
    """
    Delete a lead (soft delete)
    """
    deleted = await lead_service.delete_lead(lead_id)
    
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Lead with ID {lead_id} not found"
        )
    
    return SuccessResponse(message="Lead deleted successfully")


@router.post("/bulk", response_model=BulkOperationResponse)
async def bulk_create_leads(
    bulk_data: LeadBulkCreate,
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_user),
    lead_service: LeadService = Depends(get_lead_service)
):
    """
    Create multiple leads in bulk
    """
    results = await lead_service.bulk_create_leads(
        leads_data=[lead.dict() for lead in bulk_data.leads],
        user_id=current_user.get("user_id")
    )
    
    return BulkOperationResponse(
        total=len(bulk_data.leads),
        successful=results["successful"],
        failed=results["failed"],
        errors=results["errors"]
    )


@router.post("/search", response_model=PaginatedResponse[LeadResponse])
async def search_leads(
    search_params: LeadSearchParams,
    pagination: PaginationParams = Depends(),
    current_user: dict = Depends(get_current_user),
    lead_service: LeadService = Depends(get_lead_service)
):
    """
    Advanced search leads with multiple filters
    """
    leads, total = await lead_service.search_leads(
        search_params=search_params.dict(exclude_none=True),
        offset=pagination.offset(),
        limit=pagination.limit
    )
    
    return PaginatedResponse.create(
        items=leads,
        total=total,
        params=pagination
    )


@router.post("/export")
async def export_leads(
    export_request: LeadExportRequest,
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_user),
    lead_service: LeadService = Depends(get_lead_service)
):
    """
    Export leads to CSV, JSON, or Excel
    Returns download URL or sends to email
    """
    export_url = await lead_service.export_leads(
        format=export_request.format,
        filters=export_request.filters.dict(exclude_none=True) if export_request.filters else None,
        fields=export_request.fields,
        include_metadata=export_request.include_metadata,
        user_email=current_user.get("email")
    )
    
    return SuccessResponse(
        message=f"Export initiated. Download from: {export_url}",
        data={"download_url": export_url}
    )


@router.post("/{lead_id}/enrich", response_model=SuccessResponse)
async def enrich_lead(
    lead_id: UUID,
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_user),
    lead_service: LeadService = Depends(get_lead_service)
):
    """
    Enrich a single lead with AI
    """
    lead = await lead_service.get_lead_by_id(lead_id)
    if not lead:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Lead with ID {lead_id} not found"
        )
    
    # Trigger enrichment in background
    background_tasks.add_task(enrich_leads_task.delay, [str(lead_id)])
    
    return SuccessResponse(message="Lead enrichment started")


@router.post("/bulk/enrich", response_model=SuccessResponse)
async def bulk_enrich_leads(
    lead_ids: List[UUID],
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_user)
):
    """
    Enrich multiple leads with AI in background
    """
    if len(lead_ids) > 1000:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Maximum 1000 leads per bulk enrich operation"
        )
    
    # Trigger enrichment in background
    background_tasks.add_task(
        enrich_leads_task.delay,
        [str(lead_id) for lead_id in lead_ids]
    )
    
    return SuccessResponse(
        message=f"Enrichment started for {len(lead_ids)} leads"
    )


@router.post("/bulk/score", response_model=SuccessResponse)
async def bulk_score_leads(
    score_request: LeadScoreUpdate,
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_user)
):
    """
    Recalculate scores for leads
    """
    background_tasks.add_task(
        score_leads_task.delay,
        [str(lead_id) for lead_id in score_request.lead_ids],
        score_request.recalculate
    )
    
    return SuccessResponse(
        message=f"Scoring started for {len(score_request.lead_ids)} leads"
    )


@router.post("/{lead_id}/qualify", response_model=SuccessResponse)
async def qualify_lead(
    lead_id: UUID,
    use_ai: bool = Query(default=True),
    current_user: dict = Depends(get_current_user),
    lead_service: LeadService = Depends(get_lead_service)
):
    """
    Qualify a lead (determine if it's a good fit)
    """
    result = await lead_service.qualify_lead(
        lead_id=lead_id,
        use_ai=use_ai
    )
    
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Lead with ID {lead_id} not found"
        )
    
    return SuccessResponse(
        message=f"Lead qualified with score {result['score']}",
        data=result
    )


@router.get("/stats/summary")
async def get_lead_stats(
    campaign_id: Optional[UUID] = None,
    current_user: dict = Depends(get_current_user),
    lead_service: LeadService = Depends(get_lead_service)
):
    """
    Get lead statistics summary
    """
    stats = await lead_service.get_lead_stats(campaign_id=campaign_id)
    
    return SuccessResponse(data=stats)


@router.get("/duplicates/{lead_id}")
async def find_duplicates(
    lead_id: UUID,
    threshold: float = Query(default=0.8, ge=0.5, le=1.0),
    current_user: dict = Depends(get_current_user),
    lead_service: LeadService = Depends(get_lead_service)
):
    """
    Find duplicate leads similar to the given lead
    """
    duplicates = await lead_service.find_duplicate_leads(
        lead_id=lead_id,
        similarity_threshold=threshold
    )
    
    return SuccessResponse(
        data={"duplicates": duplicates, "count": len(duplicates)}
    )