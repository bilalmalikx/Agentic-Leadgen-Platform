"""
ChromaDB Vector Client
Manages connection and operations for vector database
"""

from typing import List, Dict, Any, Optional, Tuple
import chromadb
from chromadb.config import Settings
import uuid

from app.core.logging import get_logger
from app.core.config import settings

logger = get_logger(__name__)


class VectorClient:
    """
    Client for ChromaDB vector database operations
    """
    
    def __init__(self):
        self.client = None
        self.collection = None
        self._initialized = False
    
    async def initialize(self):
        """Initialize ChromaDB client and collection"""
        try:
            # Connect to ChromaDB
            self.client = chromadb.HttpClient(
                host=settings.chroma_host,
                port=settings.chroma_port,
                settings=Settings(
                    anonymized_telemetry=False,
                    allow_reset=True
                )
            )
            
            # Get or create collection
            self.collection = self.client.get_or_create_collection(
                name=settings.chroma_collection_name,
                metadata={"hnsw:space": "cosine"}
            )
            
            self._initialized = True
            logger.info(f"ChromaDB initialized: {settings.chroma_host}:{settings.chroma_port}")
            
        except Exception as e:
            logger.error(f"Failed to initialize ChromaDB: {e}")
            raise
    
    def is_initialized(self) -> bool:
        """Check if client is initialized"""
        return self._initialized
    
    async def add_vectors(
        self,
        ids: List[str],
        embeddings: List[List[float]],
        metadatas: List[Dict[str, Any]],
        documents: List[str]
    ) -> bool:
        """
        Add vectors to collection
        """
        if not self._initialized:
            await self.initialize()
        
        try:
            self.collection.add(
                ids=ids,
                embeddings=embeddings,
                metadatas=metadatas,
                documents=documents
            )
            logger.debug(f"Added {len(ids)} vectors to ChromaDB")
            return True
            
        except Exception as e:
            logger.error(f"Failed to add vectors: {e}")
            return False
    
    async def query_vectors(
        self,
        query_embedding: List[float],
        n_results: int = 10,
        where: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Query similar vectors
        """
        if not self._initialized:
            await self.initialize()
        
        try:
            results = self.collection.query(
                query_embeddings=[query_embedding],
                n_results=n_results,
                where=where
            )
            return results
            
        except Exception as e:
            logger.error(f"Failed to query vectors: {e}")
            return {"ids": [], "distances": [], "metadatas": [], "documents": []}
    
    async def delete_vectors(self, ids: List[str]) -> bool:
        """
        Delete vectors by IDs
        """
        if not self._initialized:
            await self.initialize()
        
        try:
            self.collection.delete(ids=ids)
            logger.debug(f"Deleted {len(ids)} vectors from ChromaDB")
            return True
            
        except Exception as e:
            logger.error(f"Failed to delete vectors: {e}")
            return False
    
    async def get_vector(self, vector_id: str) -> Optional[Dict[str, Any]]:
        """
        Get single vector by ID
        """
        if not self._initialized:
            await self.initialize()
        
        try:
            result = self.collection.get(ids=[vector_id])
            if result and result['ids']:
                return {
                    "id": result['ids'][0],
                    "metadata": result['metadatas'][0] if result['metadatas'] else {},
                    "document": result['documents'][0] if result['documents'] else None
                }
            return None
            
        except Exception as e:
            logger.error(f"Failed to get vector {vector_id}: {e}")
            return None
    
    async def get_collection_stats(self) -> Dict[str, Any]:
        """
        Get collection statistics
        """
        if not self._initialized:
            await self.initialize()
        
        try:
            count = self.collection.count()
            return {
                "collection_name": settings.chroma_collection_name,
                "vector_count": count,
                "is_initialized": self._initialized
            }
        except Exception as e:
            logger.error(f"Failed to get collection stats: {e}")
            return {
                "collection_name": settings.chroma_collection_name,
                "vector_count": 0,
                "is_initialized": self._initialized,
                "error": str(e)
            }
    
    async def delete_collection(self) -> bool:
        """
        Delete entire collection (use with caution)
        """
        if not self._initialized:
            await self.initialize()
        
        try:
            self.client.delete_collection(settings.chroma_collection_name)
            self.collection = self.client.get_or_create_collection(
                name=settings.chroma_collection_name
            )
            logger.warning(f"Collection {settings.chroma_collection_name} deleted and recreated")
            return True
            
        except Exception as e:
            logger.error(f"Failed to delete collection: {e}")
            return False
    
    async def health_check(self) -> Dict[str, Any]:
        """
        Check ChromaDB health
        """
        try:
            if not self._initialized:
                await self.initialize()
            
            stats = await self.get_collection_stats()
            return {
                "status": "healthy",
                "collection": stats["collection_name"],
                "vector_count": stats["vector_count"]
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e)
            }


# Singleton instance
_vector_client = None


async def get_vector_client() -> VectorClient:
    """Get or create vector client instance"""
    global _vector_client
    if _vector_client is None:
        _vector_client = VectorClient()
        await _vector_client.initialize()
    return _vector_client


async def init_chroma():
    """Initialize ChromaDB connection"""
    client = await get_vector_client()
    return client


async def get_chroma_health():
    """Get ChromaDB health status"""
    client = await get_vector_client()
    return await client.health_check()