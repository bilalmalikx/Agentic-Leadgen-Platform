"""
Lead Deduplicator Agent
Detects and removes duplicate leads using fuzzy matching and vector similarity
"""

from typing import List, Dict, Any, Optional, Set
from difflib import SequenceMatcher
from uuid import UUID

from app.core.logging import get_logger
from app.vector_store.similarity_search import find_similar_leads

logger = get_logger(__name__)


class LeadDeduplicatorAgent:
    """
    Agent responsible for detecting and removing duplicate leads
    Uses multiple strategies: email match, fuzzy name matching, vector similarity
    """
    
    def __init__(self):
        self.similarity_threshold = 0.85
        self.email_weight = 0.5
        self.name_weight = 0.3
        self.company_weight = 0.2
    
    async def deduplicate_batch(
        self,
        leads: List[Dict[str, Any]],
        similarity_threshold: float = 0.85,
        existing_leads: Optional[List[Dict[str, Any]]] = None
    ) -> List[Dict[str, Any]]:
        """
        Remove duplicates from a batch of leads
        Also checks against existing leads in database
        """
        logger.info(f"Deduplicating {len(leads)} leads with threshold {similarity_threshold}")
        
        self.similarity_threshold = similarity_threshold
        unique_leads = []
        seen_identifiers: Set[str] = set()
        
        for lead in leads:
            # Check if duplicate within batch
            is_duplicate, duplicate_reason = self._is_duplicate_in_batch(
                lead, unique_leads, seen_identifiers
            )
            
            # Check against existing leads if provided
            if not is_duplicate and existing_leads:
                is_duplicate, duplicate_reason = await self._is_duplicate_in_db(
                    lead, existing_leads
                )
            
            if is_duplicate:
                lead["is_duplicate"] = True
                lead["duplicate_reason"] = duplicate_reason
                lead["status"] = "duplicate"
                logger.debug(f"Duplicate found for {lead.get('email')}: {duplicate_reason}")
            else:
                lead["is_duplicate"] = False
                lead["status"] = "new"
                unique_leads.append(lead)
                self._add_identifiers(lead, seen_identifiers)
        
        logger.info(f"Deduplication complete: {len(unique_leads)} unique leads out of {len(leads)}")
        return unique_leads
    
    def _is_duplicate_in_batch(
        self,
        lead: Dict[str, Any],
        existing_leads: List[Dict[str, Any]],
        seen_identifiers: Set[str]
    ) -> tuple:
        """
        Check if lead is duplicate within current batch
        """
        email = lead.get("email", "").lower().strip()
        
        # Exact email match
        if email and email in seen_identifiers:
            return True, f"Duplicate email: {email}"
        
        # Check against existing leads in batch
        for existing in existing_leads:
            similarity = self._calculate_similarity(lead, existing)
            if similarity >= self.similarity_threshold:
                return True, f"Similarity score {similarity:.2f} exceeds threshold"
        
        return False, None
    
    async def _is_duplicate_in_db(
        self,
        lead: Dict[str, Any],
        existing_leads: List[Dict[str, Any]]
    ) -> tuple:
        """
        Check if lead is duplicate in database
        """
        email = lead.get("email", "").lower().strip()
        
        for existing in existing_leads:
            existing_email = existing.get("email", "").lower().strip()
            
            # Exact email match
            if email and existing_email and email == existing_email:
                return True, f"Duplicate email in database: {email}"
            
            # Fuzzy matching
            similarity = self._calculate_similarity(lead, existing)
            if similarity >= self.similarity_threshold:
                return True, f"Similarity score {similarity:.2f} with existing lead"
        
        return False, None
    
    def _calculate_similarity(
        self,
        lead1: Dict[str, Any],
        lead2: Dict[str, Any]
    ) -> float:
        """
        Calculate similarity score between two leads
        Returns value between 0 and 1
        """
        scores = []
        
        # Email similarity
        email1 = lead1.get("email", "").lower()
        email2 = lead2.get("email", "").lower()
        if email1 and email2:
            email_similarity = SequenceMatcher(None, email1, email2).ratio()
            scores.append(email_similarity * self.email_weight)
        
        # Name similarity
        name1 = f"{lead1.get('first_name', '')} {lead1.get('last_name', '')}".strip()
        name2 = f"{lead2.get('first_name', '')} {lead2.get('last_name', '')}".strip()
        if name1 and name2:
            name_similarity = SequenceMatcher(None, name1.lower(), name2.lower()).ratio()
            scores.append(name_similarity * self.name_weight)
        
        # Company similarity
        company1 = lead1.get("company_name", "").lower()
        company2 = lead2.get("company_name", "").lower()
        if company1 and company2:
            company_similarity = SequenceMatcher(None, company1, company2).ratio()
            scores.append(company_similarity * self.company_weight)
        
        if not scores:
            return 0.0
        
        return sum(scores)
    
    def _add_identifiers(self, lead: Dict[str, Any], seen_identifiers: Set[str]):
        """
        Add lead identifiers to seen set for future duplicate detection
        """
        email = lead.get("email", "").lower().strip()
        if email:
            seen_identifiers.add(email)
        
        # Add email domain for additional detection
        if email and "@" in email:
            domain = email.split("@")[1]
            seen_identifiers.add(f"domain:{domain}")
    
    async def find_duplicates_across_campaigns(
        self,
        lead_id: UUID,
        campaign_ids: List[UUID],
        threshold: float = 0.8
    ) -> List[Dict[str, Any]]:
        """
        Find duplicate leads across multiple campaigns using vector similarity
        """
        logger.info(f"Finding duplicates for lead {lead_id} across campaigns {campaign_ids}")
        
        try:
            similar_leads = await find_similar_leads(
                lead_id=lead_id,
                threshold=threshold,
                limit=20
            )
            
            # Filter by campaign if needed
            if campaign_ids:
                campaign_id_strs = [str(cid) for cid in campaign_ids]
                similar_leads = [
                    lead for lead in similar_leads
                    if lead.get("campaign_id") in campaign_id_strs
                ]
            
            return similar_leads
            
        except Exception as e:
            logger.error(f"Failed to find duplicates: {e}")
            return []
    
    async def merge_duplicate_leads(
        self,
        primary_lead_id: UUID,
        duplicate_lead_ids: List[UUID]
    ) -> Dict[str, Any]:
        """
        Merge duplicate leads into a single lead
        """
        logger.info(f"Merging leads: primary {primary_lead_id}, duplicates {duplicate_lead_ids}")
        
        try:
            from app.db.repositories.lead_repository import LeadRepository
            from app.core.database import get_sync_session
            
            with get_sync_session() as db:
                repo = LeadRepository(db)
                
                primary = repo.get_by_id(primary_lead_id)
                if not primary:
                    return {"success": False, "error": "Primary lead not found"}
                
                merged_data = {
                    "email": primary.email,
                    "first_name": primary.first_name,
                    "last_name": primary.last_name,
                    "company_name": primary.company_name,
                    "job_title": primary.job_title,
                    "score": primary.score,
                    "merged_from": [str(primary_lead_id)]
                }
                
                # Merge data from duplicates
                for dup_id in duplicate_lead_ids:
                    duplicate = repo.get_by_id(dup_id)
                    if duplicate:
                        # Take highest score
                        if duplicate.score > merged_data["score"]:
                            merged_data["score"] = duplicate.score
                        
                        # Merge enriched data
                        if duplicate.enriched_data:
                            merged_data.setdefault("enriched_data", {}).update(duplicate.enriched_data)
                        
                        merged_data["merged_from"].append(str(dup_id))
                        
                        # Mark duplicate as deleted
                        repo.soft_delete(dup_id)
                
                # Update primary lead with merged data
                await repo.update(primary_lead_id, {
                    "score": merged_data["score"],
                    "enriched_data": merged_data.get("enriched_data", {}),
                    "metadata": {
                        **primary.metadata,
                        "merged_from": merged_data["merged_from"],
                        "merged_at": datetime.utcnow().isoformat()
                    }
                })
                
                logger.info(f"Merged {len(duplicate_lead_ids)} duplicates into {primary_lead_id}")
                return {
                    "success": True,
                    "primary_lead_id": str(primary_lead_id),
                    "merged_count": len(duplicate_lead_ids),
                    "merged_from": merged_data["merged_from"]
                }
                
        except Exception as e:
            logger.error(f"Failed to merge duplicates: {e}")
            return {"success": False, "error": str(e)}


# Singleton instance
_deduplicator_agent = None


def get_deduplicator_agent() -> LeadDeduplicatorAgent:
    """Get or create deduplicator agent instance"""
    global _deduplicator_agent
    if _deduplicator_agent is None:
        _deduplicator_agent = LeadDeduplicatorAgent()
    return _deduplicator_agent