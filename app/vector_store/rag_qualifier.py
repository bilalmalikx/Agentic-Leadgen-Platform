"""
RAG Qualifier
Retrieval-Augmented Generation for lead qualification
Uses vector search to find similar qualified leads and LLM for decision
"""

from typing import List, Dict, Any, Optional, Tuple
from uuid import UUID
from datetime import datetime

from app.core.logging import get_logger
from app.core.config import settings
from app.vector_store.lead_index import get_lead_index
from app.vector_store.similarity_search import find_similar_leads
from app.tools.llm_failover import get_llm_client

logger = get_logger(__name__)


class RAGQualifier:
    """
    RAG-based lead qualifier that:
    1. Retrieves similar already-qualified leads from vector store
    2. Uses LLM to analyze the current lead against retrieved examples
    3. Makes qualification decision with reasoning
    """
    
    def __init__(self):
        self.lead_index = None
        self.llm_client = None
    
    async def _ensure_initialized(self):
        """Ensure dependencies are initialized"""
        if self.lead_index is None:
            self.lead_index = get_lead_index()
        if self.llm_client is None:
            self.llm_client = get_llm_client()
    
    async def qualify_lead(
        self,
        lead_data: Dict[str, Any],
        campaign_context: Optional[Dict[str, Any]] = None,
        threshold: float = 0.7,
        top_k: int = 5
    ) -> Dict[str, Any]:
        """
        Qualify a lead using RAG
        Returns qualification decision with reasoning
        """
        await self._ensure_initialized()
        
        try:
            # Step 1: Find similar qualified leads from vector store
            similar_leads = await self._retrieve_similar_qualified_leads(
                lead_data=lead_data,
                threshold=threshold,
                top_k=top_k
            )
            
            # Step 2: Build context from similar leads
            context = self._build_rag_context(
                current_lead=lead_data,
                similar_leads=similar_leads,
                campaign_context=campaign_context
            )
            
            # Step 3: Call LLM for qualification
            qualification = await self._llm_qualify(
                context=context,
                lead_data=lead_data
            )
            
            # Step 4: Add metadata to result
            qualification["similar_leads_used"] = len(similar_leads)
            qualification["rag_confidence"] = self._calculate_rag_confidence(similar_leads, qualification)
            qualification["qualified_at"] = datetime.utcnow().isoformat()
            
            logger.info(
                f"RAG qualification completed for lead {lead_data.get('email')}: "
                f"qualified={qualification.get('is_qualified')}, "
                f"confidence={qualification.get('confidence')}"
            )
            
            return qualification
            
        except Exception as e:
            logger.error(f"RAG qualification failed: {e}")
            return self._fallback_qualification(lead_data, str(e))
    
    async def qualify_batch(
        self,
        leads: List[Dict[str, Any]],
        campaign_context: Optional[Dict[str, Any]] = None,
        threshold: float = 0.7,
        top_k: int = 3
    ) -> List[Dict[str, Any]]:
        """
        Qualify multiple leads in batch
        """
        import asyncio
        
        tasks = [
            self.qualify_lead(lead, campaign_context, threshold, top_k)
            for lead in leads
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        qualified_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                qualified_results.append(self._fallback_qualification(leads[i], str(result)))
            else:
                qualified_results.append(result)
        
        return qualified_results
    
    async def _retrieve_similar_qualified_leads(
        self,
        lead_data: Dict[str, Any],
        threshold: float = 0.7,
        top_k: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Retrieve similar leads that are already qualified from vector store
        """
        try:
            # Generate embedding for current lead
            from app.vector_store.embeddings import get_embedding_generator
            embedding_gen = get_embedding_generator()
            embedding = await embedding_gen.generate_lead_embedding(lead_data)
            
            if not embedding:
                logger.warning("Failed to generate embedding for lead")
                return []
            
            # Query vector store for similar leads
            vector_client = await self.lead_index.vector_client
            results = await vector_client.query_vectors(
                query_embedding=embedding,
                n_results=top_k * 2,  # Get more for filtering
                where={"status": "qualified"}  # Only qualified leads
            )
            
            # Process and filter results
            similar_leads = []
            for i, vid in enumerate(results.get("ids", [[]])[0]):
                distance = results.get("distances", [[]])[0][i] if results.get("distances") else 0
                similarity = 1 - distance
                
                if similarity >= threshold:
                    metadata = results.get("metadatas", [[]])[0][i] if results.get("metadatas") else {}
                    
                    similar_leads.append({
                        "lead_id": vid,
                        "similarity": round(similarity, 4),
                        "email": metadata.get("email", ""),
                        "company_name": metadata.get("company_name", ""),
                        "job_title": metadata.get("job_title", ""),
                        "score": metadata.get("score", 0),
                        "document": results.get("documents", [[]])[0][i] if results.get("documents") else None
                    })
            
            return similar_leads[:top_k]
            
        except Exception as e:
            logger.error(f"Failed to retrieve similar leads: {e}")
            return []
    
    def _build_rag_context(
        self,
        current_lead: Dict[str, Any],
        similar_leads: List[Dict[str, Any]],
        campaign_context: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Build context string for LLM from similar leads
        """
        context_parts = []
        
        # Add campaign context if provided
        if campaign_context:
            context_parts.append(f"Campaign Context:")
            context_parts.append(f"- Target Industry: {campaign_context.get('industry', 'Not specified')}")
            context_parts.append(f"- Target Role: {campaign_context.get('role', 'Not specified')}")
            context_parts.append(f"- Target Company Size: {campaign_context.get('company_size', 'Not specified')}")
            context_parts.append("")
        
        # Add current lead information
        context_parts.append("Current Lead to Evaluate:")
        context_parts.append(f"- Company: {current_lead.get('company_name', 'Unknown')}")
        context_parts.append(f"- Job Title: {current_lead.get('job_title', 'Unknown')}")
        context_parts.append(f"- Industry: {current_lead.get('industry', 'Unknown')}")
        context_parts.append(f"- Company Size: {current_lead.get('company_size', 'Unknown')}")
        context_parts.append(f"- Location: {current_lead.get('location', 'Unknown')}")
        context_parts.append("")
        
        # Add similar qualified leads as examples
        if similar_leads:
            context_parts.append("Similar Already-Qualified Leads (Reference Examples):")
            for i, lead in enumerate(similar_leads, 1):
                context_parts.append(f"\nExample {i}:")
                context_parts.append(f"- Company: {lead.get('company_name', 'Unknown')}")
                context_parts.append(f"- Job Title: {lead.get('job_title', 'Unknown')}")
                context_parts.append(f"- Similarity Score: {lead.get('similarity', 0)}")
                context_parts.append(f"- Previous Score: {lead.get('score', 0)}")
        else:
            context_parts.append("No similar qualified leads found in database.")
        
        return "\n".join(context_parts)
    
    async def _llm_qualify(
        self,
        context: str,
        lead_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Use LLM to qualify lead based on context
        """
        prompt = f"""
Based on the following context and lead information, determine if this lead should be qualified.

{context}

Task: Evaluate the lead and return a JSON response with:
1. is_qualified: (true/false)
2. confidence: (High/Medium/Low)
3. score: (0-100 qualification score)
4. reasoning: (list of reasons for qualification or rejection)
5. next_steps: (list of recommended actions if qualified)
6. similar_to_example: (which example lead this is most similar to, if any)

Consider:
- How similar is this lead to already-qualified leads?
- Does it match the campaign target criteria?
- What is the decision-maker potential?
- Is the company relevant to our ICP?

Return ONLY valid JSON, no other text.
"""
        
        response = await self.llm_client.complete_with_json(
            prompt=prompt,
            system_prompt="You are a lead qualification expert using RAG (Retrieval-Augmented Generation). Analyze the lead against similar qualified leads and make a decision.",
            temperature=0.3
        )
        
        # Ensure required fields
        return {
            "is_qualified": response.get("is_qualified", False),
            "confidence": response.get("confidence", "Medium"),
            "score": min(100, max(0, response.get("score", 50))),
            "reasoning": response.get("reasoning", ["No reasoning provided"]),
            "next_steps": response.get("next_steps", ["Manual review recommended"]),
            "similar_to_example": response.get("similar_to_example"),
            "rag_method": "vector_similarity"
        }
    
    def _calculate_rag_confidence(
        self,
        similar_leads: List[Dict[str, Any]],
        qualification: Dict[str, Any]
    ) -> float:
        """
        Calculate confidence based on RAG retrieval quality
        """
        if not similar_leads:
            return 0.3  # Low confidence if no similar leads found
        
        # Average similarity of retrieved leads
        avg_similarity = sum(l.get("similarity", 0) for l in similar_leads) / len(similar_leads)
        
        # If LLM says qualified and we have good similar leads, high confidence
        if qualification.get("is_qualified") and avg_similarity > 0.8:
            return 0.9
        elif qualification.get("is_qualified") and avg_similarity > 0.6:
            return 0.7
        elif qualification.get("is_qualified"):
            return 0.5
        
        # If not qualified
        return 0.4
    
    def _fallback_qualification(self, lead_data: Dict[str, Any], error: str) -> Dict[str, Any]:
        """
        Fallback qualification when RAG fails
        """
        logger.warning(f"Using fallback qualification for {lead_data.get('email')}: {error}")
        
        # Simple rule-based fallback
        score = 0
        reasons = []
        
        # Check for email
        if lead_data.get("email"):
            score += 20
            reasons.append("Valid email present")
        
        # Check for company
        if lead_data.get("company_name"):
            score += 30
            reasons.append("Company information present")
        else:
            reasons.append("Missing company information")
        
        # Check for job title
        job_title = lead_data.get("job_title", "").lower()
        if job_title:
            decision_maker_keywords = ["ceo", "founder", "cto", "director", "vp", "head"]
            if any(keyword in job_title for keyword in decision_maker_keywords):
                score += 30
                reasons.append("Decision-maker job title detected")
            else:
                score += 15
                reasons.append("Job title present but not decision-maker")
        else:
            reasons.append("Missing job title")
        
        # Check for industry
        if lead_data.get("industry"):
            score += 20
            reasons.append("Industry information present")
        
        is_qualified = score >= 60
        
        return {
            "is_qualified": is_qualified,
            "confidence": "Low",
            "score": score,
            "reasoning": reasons + [f"RAG failed: {error[:100]}"],
            "next_steps": ["Manual review required"] if not is_qualified else ["Add to outreach queue"],
            "rag_method": "fallback_rule_based"
        }
    
    async def add_qualified_lead_to_index(
        self,
        lead_id: UUID,
        lead_data: Dict[str, Any],
        qualification_result: Dict[str, Any]
    ) -> bool:
        """
        Add a qualified lead to vector store for future RAG retrieval
        """
        await self._ensure_initialized()
        
        # Add qualification score to metadata
        lead_data["qualification_score"] = qualification_result.get("score", 0)
        lead_data["qualification_confidence"] = qualification_result.get("confidence", "Medium")
        lead_data["status"] = "qualified"
        
        # Add to index
        return await self.lead_index.add_lead(lead_id, lead_data)
    
    async def get_qualification_explanation(
        self,
        lead_id: UUID,
        qualification_result: Dict[str, Any]
    ) -> str:
        """
        Generate human-readable explanation of qualification decision
        """
        explanation_parts = []
        
        explanation_parts.append(f"Qualification Decision: {'QUALIFIED' if qualification_result.get('is_qualified') else 'NOT QUALIFIED'}")
        explanation_parts.append(f"Confidence: {qualification_result.get('confidence')}")
        explanation_parts.append(f"Score: {qualification_result.get('score')}/100")
        explanation_parts.append("")
        explanation_parts.append("Reasons:")
        for reason in qualification_result.get("reasoning", []):
            explanation_parts.append(f"  • {reason}")
        
        explanation_parts.append("")
        explanation_parts.append("Recommended Next Steps:")
        for step in qualification_result.get("next_steps", []):
            explanation_parts.append(f"  • {step}")
        
        if qualification_result.get("similar_to_example"):
            explanation_parts.append("")
            explanation_parts.append(f"Similar to example lead: {qualification_result.get('similar_to_example')}")
        
        explanation_parts.append("")
        explanation_parts.append(f"Method: {qualification_result.get('rag_method', 'unknown')}")
        explanation_parts.append(f"Similar Leads Used: {qualification_result.get('similar_leads_used', 0)}")
        
        return "\n".join(explanation_parts)


# Singleton instance
_rag_qualifier = None


def get_rag_qualifier() -> RAGQualifier:
    """Get or create RAG qualifier instance"""
    global _rag_qualifier
    if _rag_qualifier is None:
        _rag_qualifier = RAGQualifier()
    return _rag_qualifier


async def qualify_lead_with_rag(
    lead_data: Dict[str, Any],
    campaign_context: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Quick function to qualify a lead using RAG
    """
    qualifier = get_rag_qualifier()
    return await qualifier.qualify_lead(lead_data, campaign_context)