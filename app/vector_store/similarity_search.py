"""
Similarity Search
Advanced similarity search for leads with filtering
"""

from typing import List, Dict, Any, Optional, Tuple
from uuid import UUID

from app.core.logging import get_logger
from app.vector_store.lead_index import get_lead_index
from app.vector_store.embeddings import get_embedding_generator

logger = get_logger(__name__)


async def find_similar_leads(
    lead_id: UUID,
    threshold: float = 0.7,
    limit: int = 10,
    filter_by_status: Optional[List[str]] = None,
    filter_by_quality: Optional[List[str]] = None
) -> List[Dict[str, Any]]:
    """
    Find leads similar to given lead with optional filters
    """
    index = get_lead_index()
    
    similar = await index.find_similar_leads(
        lead_id=lead_id,
        threshold=threshold,
        limit=limit * 2  # Get more for filtering
    )
    
    # Apply filters if needed
    if filter_by_status or filter_by_quality:
        filtered = []
        for lead in similar:
            if filter_by_status and lead.get("status") not in filter_by_status:
                continue
            if filter_by_quality and lead.get("quality") not in filter_by_quality:
                continue
            filtered.append(lead)
        
        return filtered[:limit]
    
    return similar[:limit]


async def search_leads_by_text(
    query: str,
    threshold: float = 0.5,
    limit: int = 20,
    filter_campaign_id: Optional[UUID] = None
) -> List[Dict[str, Any]]:
    """
    Search leads by text query with semantic search
    """
    index = get_lead_index()
    
    results = await index.search_by_text(
        query=query,
        threshold=threshold,
        limit=limit
    )
    
    # Filter by campaign if needed
    if filter_campaign_id:
        filtered = []
        for result in results:
            # Check campaign from database (simplified)
            # In production, store campaign_id in metadata
            filtered.append(result)
        return filtered[:limit]
    
    return results


async def find_duplicate_leads(
    lead_email: str,
    similarity_threshold: float = 0.85,
    limit: int = 5
) -> List[Dict[str, Any]]:
    """
    Find duplicate leads using email similarity
    """
    # Use email as search query
    results = await search_leads_by_text(
        query=lead_email,
        threshold=similarity_threshold,
        limit=limit + 1
    )
    
    # Filter out the exact match if present
    duplicates = []
    for result in results:
        if result.get("email", "").lower() != lead_email.lower():
            duplicates.append(result)
    
    return duplicates[:limit]


async def get_most_similar_lead(
    lead_data: Dict[str, Any],
    exclude_id: Optional[UUID] = None
) -> Optional[Dict[str, Any]]:
    """
    Get the single most similar lead to given lead data
    """
    embedding_gen = get_embedding_generator()
    index = get_lead_index()
    
    # Generate embedding for lead data
    embedding = await embedding_gen.generate_lead_embedding(lead_data)
    
    if not embedding:
        return None
    
    # Query vectors
    vector_client = await index.vector_client
    results = await vector_client.query_vectors(
        query_embedding=embedding,
        n_results=2
    )
    
    # Get the best match
    if results.get("ids") and results[0]:
        best_id = results["ids"][0][0]
        if exclude_id and str(exclude_id) == best_id:
            if len(results["ids"][0]) > 1:
                best_id = results["ids"][0][1]
            else:
                return None
        
        metadata = results.get("metadatas", [[]])[0][0] if results.get("metadatas") else {}
        
        return {
            "lead_id": UUID(best_id),
            "similarity": 1 - results["distances"][0][0] if results.get("distances") else 0,
            "email": metadata.get("email", ""),
            "company_name": metadata.get("company_name", ""),
            "job_title": metadata.get("job_title", "")
        }
    
    return None


async def batch_similarity_search(
    lead_ids: List[UUID],
    threshold: float = 0.7,
    limit_per_lead: int = 5
) -> Dict[UUID, List[Dict[str, Any]]]:
    """
    Find similar leads for multiple leads in batch
    """
    import asyncio
    
    tasks = [
        find_similar_leads(lead_id, threshold, limit_per_lead)
        for lead_id in lead_ids
    ]
    
    results = await asyncio.gather(*tasks)
    
    return {
        lead_id: result for lead_id, result in zip(lead_ids, results)
    }


async def get_lead_clusters(
    campaign_id: UUID,
    n_clusters: int = 5,
    min_similarity: float = 0.6
) -> List[Dict[str, Any]]:
    """
    Group leads into clusters based on similarity
    (Simplified clustering - for production use proper clustering)
    """
    from app.db.session import get_sync_session
    from app.db.repositories.lead_repository import LeadRepository
    
    with get_sync_session() as db:
        repo = LeadRepository(db)
        leads, total = await repo.get_by_campaign(campaign_id, limit=1000)
    
    if not leads:
        return []
    
    # Simple clustering based on company name
    clusters = {}
    
    for lead in leads:
        company = lead.company_name or "Unknown"
        
        if company not in clusters:
            clusters[company] = []
        
        clusters[company].append({
            "lead_id": str(lead.id),
            "email": lead.email,
            "score": lead.score
        })
    
    # Convert to list format
    result = []
    for company, leads_list in clusters.items():
        result.append({
            "cluster_name": company,
            "lead_count": len(leads_list),
            "average_score": sum(l["score"] for l in leads_list) / len(leads_list) if leads_list else 0,
            "leads": leads_list[:10]  # Limit to 10 per cluster
        })
    
    # Sort by lead count
    result.sort(key=lambda x: x["lead_count"], reverse=True)
    
    return result[:n_clusters]