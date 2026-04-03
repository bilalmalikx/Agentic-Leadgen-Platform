"""
Campaign Endpoints
Create, manage, and track lead generation campaigns
"""

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, status
from typing import List, Optional
from uuid import UUID

from app.api.dependencies import get_current_user, get_campaign_service
from app.schemas.campaign import (
    CampaignCreate, CampaignUpdate, CampaignResponse, CampaignDetailResponse,
    CampaignStatsResponse, CampaignStartRequest, CampaignDuplicateRequest
)
from app.schemas.lead import LeadResponse
from app.schemas.common import (
    SuccessResponse, PaginatedResponse, PaginationParams, IDResponse
)
from app.services.campaign_service import CampaignService
from app.core.logging import get_logger
from app.workers.lead_tasks import generate_leads_task

router = APIRouter()
logger = get_logger(__name__)


@router.get("/", response_model=PaginatedResponse[CampaignResponse])
async def get_campaigns(
    status: Optional[str] = None,
    pagination: PaginationParams = Depends(),
    current_user: dict = Depends(get_current_user),
    campaign_service: CampaignService = Depends(get_campaign_service)
):
    """
    Get list of campaigns with filtering
    """
    campaigns, total = await campaign_service.get_campaigns(
        user_id=current_user.get("user_id"),
        status=status,
        offset=pagination.offset(),
        limit=pagination.limit
    )
    
    return PaginatedResponse.create(
        items=campaigns,
        total=total,
        params=pagination
    )


@router.get("/{campaign_id}", response_model=CampaignDetailResponse)
async def get_campaign(
    campaign_id: UUID,
    current_user: dict = Depends(get_current_user),
    campaign_service: CampaignService = Depends(get_campaign_service)
):
    """
    Get campaign by ID with full details
    """
    campaign = await campaign_service.get_campaign_by_id(
        campaign_id=campaign_id,
        user_id=current_user.get("user_id")
    )
    
    if not campaign:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Campaign with ID {campaign_id} not found"
        )
    
    return campaign


@router.post("/", response_model=IDResponse, status_code=status.HTTP_201_CREATED)
async def create_campaign(
    campaign_data: CampaignCreate,
    current_user: dict = Depends(get_current_user),
    campaign_service: CampaignService = Depends(get_campaign_service)
):
    """
    Create a new lead generation campaign
    """
    campaign = await campaign_service.create_campaign(
        campaign_data=campaign_data.dict(),
        user_id=current_user.get("user_id")
    )
    
    return IDResponse(id=campaign.id, message="Campaign created successfully")


@router.put("/{campaign_id}", response_model=SuccessResponse)
async def update_campaign(
    campaign_id: UUID,
    campaign_data: CampaignUpdate,
    current_user: dict = Depends(get_current_user),
    campaign_service: CampaignService = Depends(get_campaign_service)
):
    """
    Update an existing campaign
    """
    updated = await campaign_service.update_campaign(
        campaign_id=campaign_id,
        update_data=campaign_data.dict(exclude_none=True),
        user_id=current_user.get("user_id")
    )
    
    if not updated:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Campaign with ID {campaign_id} not found"
        )
    
    return SuccessResponse(message="Campaign updated successfully")


@router.delete("/{campaign_id}", response_model=SuccessResponse)
async def delete_campaign(
    campaign_id: UUID,
    current_user: dict = Depends(get_current_user),
    campaign_service: CampaignService = Depends(get_campaign_service)
):
    """
    Delete a campaign (soft delete)
    """
    deleted = await campaign_service.delete_campaign(
        campaign_id=campaign_id,
        user_id=current_user.get("user_id")
    )
    
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Campaign with ID {campaign_id} not found"
        )
    
    return SuccessResponse(message="Campaign deleted successfully")


@router.post("/{campaign_id}/start", response_model=SuccessResponse)
async def start_campaign(
    campaign_id: UUID,
    start_request: CampaignStartRequest,
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_user),
    campaign_service: CampaignService = Depends(get_campaign_service)
):
    """
    Start a campaign to generate leads
    """
    campaign = await campaign_service.get_campaign_by_id(campaign_id)
    
    if not campaign:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Campaign with ID {campaign_id} not found"
        )
    
    if campaign.status == "running":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Campaign is already running"
        )
    
    if start_request.start_now:
        # Start immediately
        await campaign_service.start_campaign(campaign_id)
        
        # Trigger Celery task in background
        background_tasks.add_task(
            generate_leads_task.delay,
            str(campaign_id)
        )
        
        message = "Campaign started successfully"
    else:
        # Schedule for later
        await campaign_service.schedule_campaign(
            campaign_id=campaign_id,
            scheduled_at=start_request.scheduled_start_at
        )
        message = f"Campaign scheduled for {start_request.scheduled_start_at}"
    
    return SuccessResponse(message=message)


@router.post("/{campaign_id}/pause", response_model=SuccessResponse)
async def pause_campaign(
    campaign_id: UUID,
    current_user: dict = Depends(get_current_user),
    campaign_service: CampaignService = Depends(get_campaign_service)
):
    """
    Pause a running campaign
    """
    paused = await campaign_service.pause_campaign(campaign_id)
    
    if not paused:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Campaign cannot be paused (not running)"
        )
    
    return SuccessResponse(message="Campaign paused successfully")


@router.post("/{campaign_id}/resume", response_model=SuccessResponse)
async def resume_campaign(
    campaign_id: UUID,
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_user),
    campaign_service: CampaignService = Depends(get_campaign_service)
):
    """
    Resume a paused campaign
    """
    resumed = await campaign_service.resume_campaign(campaign_id)
    
    if not resumed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Campaign cannot be resumed (not paused)"
        )
    
    # Resume Celery task
    background_tasks.add_task(
        generate_leads_task.delay,
        str(campaign_id)
    )
    
    return SuccessResponse(message="Campaign resumed successfully")


@router.post("/{campaign_id}/cancel", response_model=SuccessResponse)
async def cancel_campaign(
    campaign_id: UUID,
    current_user: dict = Depends(get_current_user),
    campaign_service: CampaignService = Depends(get_campaign_service)
):
    """
    Cancel a campaign (running or scheduled)
    """
    cancelled = await campaign_service.cancel_campaign(campaign_id)
    
    if not cancelled:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Campaign cannot be cancelled"
        )
    
    return SuccessResponse(message="Campaign cancelled successfully")


@router.get("/{campaign_id}/leads", response_model=PaginatedResponse[LeadResponse])
async def get_campaign_leads(
    campaign_id: UUID,
    pagination: PaginationParams = Depends(),
    current_user: dict = Depends(get_current_user),
    campaign_service: CampaignService = Depends(get_campaign_service)
):
    """
    Get all leads generated by a campaign
    """
    leads, total = await campaign_service.get_campaign_leads(
        campaign_id=campaign_id,
        offset=pagination.offset(),
        limit=pagination.limit
    )
    
    return PaginatedResponse.create(
        items=leads,
        total=total,
        params=pagination
    )


@router.get("/{campaign_id}/stats", response_model=CampaignStatsResponse)
async def get_campaign_stats(
    campaign_id: UUID,
    current_user: dict = Depends(get_current_user),
    campaign_service: CampaignService = Depends(get_campaign_service)
):
    """
    Get detailed statistics for a campaign
    """
    stats = await campaign_service.get_campaign_stats(campaign_id)
    
    if not stats:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Campaign with ID {campaign_id} not found"
        )
    
    return stats


@router.post("/{campaign_id}/duplicate", response_model=IDResponse)
async def duplicate_campaign(
    campaign_id: UUID,
    duplicate_request: CampaignDuplicateRequest,
    current_user: dict = Depends(get_current_user),
    campaign_service: CampaignService = Depends(get_campaign_service)
):
    """
    Duplicate an existing campaign
    """
    new_campaign = await campaign_service.duplicate_campaign(
        campaign_id=campaign_id,
        new_name=duplicate_request.new_name,
        copy_leads=duplicate_request.copy_leads,
        user_id=current_user.get("user_id")
    )
    
    return IDResponse(
        id=new_campaign.id,
        message=f"Campaign duplicated successfully. New campaign ID: {new_campaign.id}"
    )


@router.get("/stats/overall")
async def get_overall_stats(
    current_user: dict = Depends(get_current_user),
    campaign_service: CampaignService = Depends(get_campaign_service)
):
    """
    Get overall statistics across all campaigns
    """
    stats = await campaign_service.get_overall_stats(
        user_id=current_user.get("user_id")
    )
    
    return SuccessResponse(data=stats)