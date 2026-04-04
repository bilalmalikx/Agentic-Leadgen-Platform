"""
Lead Index
Manages lead vectors in ChromaDB for similarity search
"""

from typing import List, Dict, Any, Optional, Tuple
from uuid import UUID
import json

from app.core.logging import get_logger
from app.vector_store.vector_client import get_vector_client
from app.vector_store.embeddings import get_embedding_generator
from app.core.database import get_sync_session

logger = get_logger(__name__)


class LeadIndex:
    """
    Index for lead vectors to enable semantic search
    """
    
    def __init__(self):
        self.vector_client = None
        self.embedding_generator = None
    
    async def _ensure_initialized(self):
        """Ensure vector client and embedding generator are initialized"""
        if self.vector_client is None:
            self.vector_client = await get_vector_client()
        if self.embedding_generator is None:
            self.embedding_generator = get_embedding_generator()
    
    async def add_lead(self, lead_id: UUID, lead_data: Dict[str, Any]) -> bool:
        """
        Add lead to vector index
        """
        await self._ensure_initialized()
        
        try:
            # Generate embedding for lead
            embedding = await self.embedding_generator.generate_lead_embedding(lead_data)
            
            if not embedding:
                logger.warning(f"Failed to generate embedding for lead {lead_id}")
                return False
            
            # Prepare metadata
            metadata = {
                "lead_id": str(lead_id),
                "email": lead_data.get("email", ""),
                "company_name": lead_data.get("company_name", ""),
                "job_title": lead_data.get("job_title", ""),
                "score": lead_data.get("score", 0),
                "status": lead_data.get("status", "new"),
                "quality": lead_data.get("quality", "unqualified")
            }
            
            # Prepare document (text representation)
            document = self._lead_to_text(lead_data)
            
            # Add to vector store
            success = await self.vector_client.add_vectors(
                ids=[str(lead_id)],
                embeddings=[embedding],
                metadatas=[metadata],
                documents=[document]
            )
            
            if success:
                logger.debug(f"Lead {lead_id} added to vector index")
            
            return success
            
        except Exception as e:
            logger.error(f"Failed to add lead {lead_id} to index: {e}")
            return False
    
    async def add_leads_batch(self, leads: List[Tuple[UUID, Dict[str, Any]]]) -> int:
        """
        Add multiple leads to vector index in batch
        """
        await self._ensure_initialized()
        
        successful = 0
        
        for lead_id, lead_data in leads:
            if await self.add_lead(lead_id, lead_data):
                successful += 1
        
        logger.info(f"Added {successful}/{len(leads)} leads to vector index")
        return successful
    
    async def remove_lead(self, lead_id: UUID) -> bool:
        """
        Remove lead from vector index
        """
        await self._ensure_initialized()
        
        try:
            return await self.vector_client.delete_vectors([str(lead_id)])
        except Exception as e:
            logger.error(f"Failed to remove lead {lead_id} from index: {e}")
            return False
    
    async def find_similar_leads(
        self,
        lead_id: UUID,
        threshold: float = 0.7,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Find leads similar to given lead
        """
        await self._ensure_initialized()
        
        try:
            # Get lead data from database
            lead_data = await self._get_lead_data(lead_id)
            if not lead_data:
                logger.warning(f"Lead {lead_id} not found in database")
                return []
            
            # Generate embedding for the lead
            embedding = await self.embedding_generator.generate_lead_embedding(lead_data)
            
            if not embedding:
                return []
            
            # Query similar vectors
            results = await self.vector_client.query_vectors(
                query_embedding=embedding,
                n_results=limit + 1  # +1 because it will include the lead itself
            )
            
            # Process results
            similar_leads = []
            for i, vid in enumerate(results.get("ids", [[]])[0]):
                if vid == str(lead_id):
                    continue  # Skip the lead itself
                
                distance = results.get("distances", [[]])[0][i] if results.get("distances") else 0
                similarity = 1 - distance  # Convert distance to similarity
                
                if similarity >= threshold:
                    metadata = results.get("metadatas", [[]])[0][i] if results.get("metadatas") else {}
                    
                    similar_leads.append({
                        "lead_id": UUID(vid),
                        "similarity": round(similarity, 4),
                        "email": metadata.get("email", ""),
                        "company_name": metadata.get("company_name", ""),
                        "job_title": metadata.get("job_title", ""),
                        "score": metadata.get("score", 0)
                    })
            
            return similar_leads[:limit]
            
        except Exception as e:
            logger.error(f"Failed to find similar leads for {lead_id}: {e}")
            return []
    
    async def search_by_text(
        self,
        query: str,
        threshold: float = 0.5,
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """
        Search leads by text query using semantic search
        """
        await self._ensure_initialized()
        
        try:
            # Generate embedding for query
            embedding = await self.embedding_generator.generate_search_embedding(query)
            
            if not embedding:
                return []
            
            # Query vectors
            results = await self.vector_client.query_vectors(
                query_embedding=embedding,
                n_results=limit
            )
            
            # Process results
            similar_leads = []
            for i, vid in enumerate(results.get("ids", [[]])[0]):
                distance = results.get("distances", [[]])[0][i] if results.get("distances") else 0
                similarity = 1 - distance
                
                if similarity >= threshold:
                    metadata = results.get("metadatas", [[]])[0][i] if results.get("metadatas") else {}
                    
                    similar_leads.append({
                        "lead_id": UUID(vid),
                        "similarity": round(similarity, 4),
                        "email": metadata.get("email", ""),
                        "company_name": metadata.get("company_name", ""),
                        "job_title": metadata.get("job_title", ""),
                        "score": metadata.get("score", 0),
                        "document": results.get("documents", [[]])[0][i] if results.get("documents") else None
                    })
            
            return similar_leads
            
        except Exception as e:
            logger.error(f"Failed to search leads by text: {e}")
            return []
    
    async def update_lead(self, lead_id: UUID, lead_data: Dict[str, Any]) -> bool:
        """
        Update lead in vector index (remove and re-add)
        """
        await self._ensure_initialized()
        
        # Remove old
        await self.remove_lead(lead_id)
        
        # Add updated
        return await self.add_lead(lead_id, lead_data)
    
    async def get_index_stats(self) -> Dict[str, Any]:
        """
        Get index statistics
        """
        await self._ensure_initialized()
        
        return await self.vector_client.get_collection_stats()
    
    def _lead_to_text(self, lead_data: Dict[str, Any]) -> str:
        """
        Convert lead data to text representation for embedding
        """
        parts = []
        
        if lead_data.get("company_name"):
            parts.append(f"Company: {lead_data['company_name']}")
        
        if lead_data.get("job_title"):
            parts.append(f"Title: {lead_data['job_title']}")
        
        if lead_data.get("industry"):
            parts.append(f"Industry: {lead_data['industry']}")
        
        if lead_data.get("skills"):
            skills = lead_data['skills']
            if isinstance(skills, list):
                parts.append(f"Skills: {', '.join(skills)}")
            else:
                parts.append(f"Skills: {skills}")
        
        if lead_data.get("company_description"):
            parts.append(f"Description: {lead_data['company_description'][:500]}")
        
        if lead_data.get("tech_stack"):
            tech_stack = lead_data['tech_stack']
            if isinstance(tech_stack, list):
                parts.append(f"Tech Stack: {', '.join(tech_stack)}")
        
        return " | ".join(parts) if parts else lead_data.get("email", "")
    
    async def _get_lead_data(self, lead_id: UUID) -> Optional[Dict[str, Any]]:
        """Get lead data from database"""
        try:
            with get_sync_session() as db:
                from app.db.repositories.lead_repository import LeadRepository
                repo = LeadRepository(db)
                lead = repo.get_by_id(lead_id)
                
                if lead:
                    return {
                        "email": lead.email,
                        "company_name": lead.company_name,
                        "job_title": lead.job_title,
                        "industry": lead.industry,
                        "score": lead.score,
                        "status": lead.status.value if lead.status else None,
                        "quality": lead.quality.value if lead.quality else None,
                        "skills": lead.metadata.get("skills", []),
                        "company_description": lead.metadata.get("company_description", ""),
                        "tech_stack": lead.tech_stack or []
                    }
            return None
        except Exception as e:
            logger.error(f"Failed to get lead data for {lead_id}: {e}")
            return None


# Singleton instance
_lead_index = None


def get_lead_index() -> LeadIndex:
    """Get or create lead index instance"""
    global _lead_index
    if _lead_index is None:
        _lead_index = LeadIndex()
    return _lead_index


async def add_lead_to_index(lead) -> bool:
    """Quick function to add lead to index"""
    index = get_lead_index()
    return await index.add_lead(lead.id, {
        "email": lead.email,
        "company_name": lead.company_name,
        "job_title": lead.job_title,
        "industry": lead.industry,
        "score": lead.score,
        "status": lead.status.value if lead.status else None,
        "quality": lead.quality.value if lead.quality else None,
        "skills": lead.metadata.get("skills", []),
        "company_description": lead.metadata.get("company_description", ""),
        "tech_stack": lead.tech_stack or []
    })