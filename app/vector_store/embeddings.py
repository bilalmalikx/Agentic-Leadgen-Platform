"""
Embeddings Generator
Generates vector embeddings for text using OpenAI or local models
"""

from typing import List, Union, Optional
import asyncio
from openai import AsyncOpenAI

from app.core.logging import get_logger
from app.core.config import settings

logger = get_logger(__name__)


class EmbeddingGenerator:
    """
    Generates embeddings for text using configured model
    Supports OpenAI and local embedding models
    """
    
    def __init__(self):
        self.model = settings.embedding_model
        self.client = AsyncOpenAI(
            api_key=settings.llm_failover.openai_api_key,
            timeout=30.0
        )
    
    async def generate_embedding(self, text: str) -> Optional[List[float]]:
        """
        Generate embedding for single text
        """
        if not text:
            return None
        
        try:
            response = await self.client.embeddings.create(
                model=self.model,
                input=text[:8000]  # Truncate to max length
            )
            
            embedding = response.data[0].embedding
            logger.debug(f"Generated embedding for text of length {len(text)}")
            return embedding
            
        except Exception as e:
            logger.error(f"Failed to generate embedding: {e}")
            return None
    
    async def generate_embeddings_batch(
        self,
        texts: List[str],
        batch_size: int = 20
    ) -> List[Optional[List[float]]]:
        """
        Generate embeddings for multiple texts in batch
        """
        embeddings = []
        
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            batch_embeddings = await asyncio.gather(
                *[self.generate_embedding(text) for text in batch]
            )
            embeddings.extend(batch_embeddings)
        
        return embeddings
    
    async def generate_lead_embedding(
        self,
        lead_data: dict,
        include_fields: List[str] = None
    ) -> Optional[List[float]]:
        """
        Generate embedding for lead data
        Combines relevant fields into a single text
        """
        default_fields = [
            "company_name", "job_title", "industry",
            "skills", "location", "company_description"
        ]
        
        fields = include_fields or default_fields
        
        # Build text from lead data
        text_parts = []
        for field in fields:
            value = lead_data.get(field, "")
            if value:
                if isinstance(value, list):
                    value = " ".join(value)
                text_parts.append(str(value))
        
        combined_text = " ".join(text_parts)
        
        if not combined_text:
            combined_text = lead_data.get("email", "")
        
        return await self.generate_embedding(combined_text)
    
    async def generate_search_embedding(self, query: str) -> Optional[List[float]]:
        """
        Generate embedding for search query
        """
        return await self.generate_embedding(query)
    
    def cosine_similarity(self, embedding1: List[float], embedding2: List[float]) -> float:
        """
        Calculate cosine similarity between two embeddings
        """
        import numpy as np
        
        vec1 = np.array(embedding1)
        vec2 = np.array(embedding2)
        
        dot_product = np.dot(vec1, vec2)
        norm1 = np.linalg.norm(vec1)
        norm2 = np.linalg.norm(vec2)
        
        if norm1 == 0 or norm2 == 0:
            return 0.0
        
        return float(dot_product / (norm1 * norm2))


# Singleton instance
_embedding_generator = None


def get_embedding_generator() -> EmbeddingGenerator:
    """Get or create embedding generator instance"""
    global _embedding_generator
    if _embedding_generator is None:
        _embedding_generator = EmbeddingGenerator()
    return _embedding_generator