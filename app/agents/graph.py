"""
LangGraph Workflow Orchestrator
Coordinates all agents for lead generation pipeline
"""

from typing import TypedDict, List, Dict, Any, Optional
from langgraph.graph import StateGraph, END
from langgraph.checkpoint import MemorySaver
import asyncio
from datetime import datetime

from app.core.logging import get_logger
from app.core.config import settings

logger = get_logger(__name__)


# Define state schema
class LeadGenerationState(TypedDict):
    """State maintained throughout the workflow"""
    campaign_id: str
    query: str
    sources: List[str]
    target_count: int
    current_page: int
    scraped_leads: List[Dict[str, Any]]
    enriched_leads: List[Dict[str, Any]]
    scored_leads: List[Dict[str, Any]]
    qualified_leads: List[Dict[str, Any]]
    deduplicated_leads: List[Dict[str, Any]]
    final_leads: List[Dict[str, Any]]
    errors: List[str]
    status: str
    started_at: str
    completed_at: Optional[str]


class LeadGenerationGraph:
    """
    LangGraph workflow for lead generation
    Orchestrates scraping -> enrichment -> scoring -> qualification -> deduplication
    """
    
    def __init__(self):
        self.logger = logger
        self.graph = self._build_graph()
        self.memory = MemorySaver()
    
    def _build_graph(self) -> StateGraph:
        """Build the LangGraph workflow"""
        
        # Create graph
        workflow = StateGraph(LeadGenerationState)
        
        # Add nodes (each node is an agent)
        workflow.add_node("scrape_leads", self.scrape_leads_node)
        workflow.add_node("enrich_leads", self.enrich_leads_node)
        workflow.add_node("score_leads", self.score_leads_node)
        workflow.add_node("qualify_leads", self.qualify_leads_node)
        workflow.add_node("deduplicate_leads", self.deduplicate_leads_node)
        workflow.add_node("save_leads", self.save_leads_node)
        workflow.add_node("handle_error", self.handle_error_node)
        
        # Set entry point
        workflow.set_entry_point("scrape_leads")
        
        # Add conditional edges
        workflow.add_conditional_edges(
            "scrape_leads",
            self.should_continue_after_scrape,
            {
                "continue": "enrich_leads",
                "error": "handle_error",
                "retry": "scrape_leads"
            }
        )
        
        workflow.add_conditional_edges(
            "enrich_leads",
            self.should_continue_after_enrich,
            {
                "continue": "score_leads",
                "error": "handle_error"
            }
        )
        
        workflow.add_conditional_edges(
            "score_leads",
            self.should_continue_after_score,
            {
                "continue": "qualify_leads",
                "error": "handle_error"
            }
        )
        
        workflow.add_conditional_edges(
            "qualify_leads",
            self.should_continue_after_qualify,
            {
                "continue": "deduplicate_leads",
                "error": "handle_error"
            }
        )
        
        workflow.add_conditional_edges(
            "deduplicate_leads",
            self.should_continue_after_dedupe,
            {
                "continue": "save_leads",
                "error": "handle_error"
            }
        )
        
        # Add edges to end
        workflow.add_edge("save_leads", END)
        workflow.add_edge("handle_error", END)
        
        return workflow.compile(checkpointer=self.memory)
    
    async def scrape_leads_node(self, state: LeadGenerationState) -> LeadGenerationState:
        """
        Node 1: Scrape leads from multiple sources
        """
        self.logger.info(f"Scraping leads for campaign {state['campaign_id']}")
        
        try:
            from app.agents.lead_scraper import LeadScraperAgent
            
            scraper = LeadScraperAgent()
            scraped_leads = await scraper.scrape(
                query=state["query"],
                sources=state["sources"],
                limit=state["target_count"]
            )
            
            state["scraped_leads"] = scraped_leads
            state["status"] = "scraped"
            self.logger.info(f"Scraped {len(scraped_leads)} leads")
            
        except Exception as e:
            self.logger.error(f"Scraping failed: {e}")
            state["errors"].append(f"Scraping error: {str(e)}")
            state["status"] = "scrape_failed"
        
        return state
    
    async def enrich_leads_node(self, state: LeadGenerationState) -> LeadGenerationState:
        """
        Node 2: Enrich leads using AI
        """
        self.logger.info(f"Enriching {len(state['scraped_leads'])} leads")
        
        try:
            from app.agents.lead_enricher import LeadEnricherAgent
            
            enricher = LeadEnricherAgent()
            enriched_leads = await enricher.enrich_batch(
                leads=state["scraped_leads"]
            )
            
            state["enriched_leads"] = enriched_leads
            state["status"] = "enriched"
            self.logger.info(f"Enriched {len(enriched_leads)} leads")
            
        except Exception as e:
            self.logger.error(f"Enrichment failed: {e}")
            state["errors"].append(f"Enrichment error: {str(e)}")
            state["status"] = "enrich_failed"
        
        return state
    
    async def score_leads_node(self, state: LeadGenerationState) -> LeadGenerationState:
        """
        Node 3: Score leads based on multiple criteria
        """
        self.logger.info(f"Scoring {len(state['enriched_leads'])} leads")
        
        try:
            from app.agents.lead_scorer import LeadScorerAgent
            
            scorer = LeadScorerAgent()
            scored_leads = await scorer.score_batch(
                leads=state["enriched_leads"]
            )
            
            state["scored_leads"] = scored_leads
            state["status"] = "scored"
            self.logger.info(f"Scored {len(scored_leads)} leads")
            
        except Exception as e:
            self.logger.error(f"Scoring failed: {e}")
            state["errors"].append(f"Scoring error: {str(e)}")
            state["status"] = "score_failed"
        
        return state
    
    async def qualify_leads_node(self, state: LeadGenerationState) -> LeadGenerationState:
        """
        Node 4: Qualify leads (AI-based or rule-based)
        """
        self.logger.info(f"Qualifying {len(state['scored_leads'])} leads")
        
        try:
            from app.agents.lead_qualifier import LeadQualifierAgent
            
            qualifier = LeadQualifierAgent()
            qualified_leads = await qualifier.qualify_batch(
                leads=state["scored_leads"],
                threshold=60  # Minimum score to qualify
            )
            
            state["qualified_leads"] = qualified_leads
            state["status"] = "qualified"
            self.logger.info(f"Qualified {len(qualified_leads)} leads")
            
        except Exception as e:
            self.logger.error(f"Qualification failed: {e}")
            state["errors"].append(f"Qualification error: {str(e)}")
            state["status"] = "qualify_failed"
        
        return state
    
    async def deduplicate_leads_node(self, state: LeadGenerationState) -> LeadGenerationState:
        """
        Node 5: Remove duplicate leads
        """
        self.logger.info(f"Deduplicating {len(state['qualified_leads'])} leads")
        
        try:
            from app.agents.lead_deduplicator import LeadDeduplicatorAgent
            
            deduplicator = LeadDeduplicatorAgent()
            deduplicated_leads = await deduplicator.deduplicate_batch(
                leads=state["qualified_leads"],
                similarity_threshold=0.85
            )
            
            state["deduplicated_leads"] = deduplicated_leads
            state["status"] = "deduplicated"
            self.logger.info(f"After deduplication: {len(deduplicated_leads)} leads")
            
        except Exception as e:
            self.logger.error(f"Deduplication failed: {e}")
            state["errors"].append(f"Deduplication error: {str(e)}")
            state["status"] = "dedupe_failed"
        
        return state
    
    async def save_leads_node(self, state: LeadGenerationState) -> LeadGenerationState:
        """
        Node 6: Save leads to database and vector store
        """
        self.logger.info(f"Saving {len(state['deduplicated_leads'])} leads to database")
        
        try:
            from app.db.repositories.lead_repository import LeadRepository
            from app.core.database import get_sync_session
            
            with get_sync_session() as db:
                repo = LeadRepository(db)
                
                saved_count = 0
                for lead_data in state["deduplicated_leads"]:
                    lead_data["campaign_id"] = state["campaign_id"]
                    lead = repo.create(lead_data)
                    saved_count += 1
                    
                    # Also save to vector store
                    from app.vector_store.lead_index import add_lead_to_index
                    add_lead_to_index(lead)
                
                state["final_leads"] = state["deduplicated_leads"]
                state["status"] = "completed"
                state["completed_at"] = datetime.utcnow().isoformat()
                
                self.logger.info(f"Saved {saved_count} leads to database")
            
        except Exception as e:
            self.logger.error(f"Saving failed: {e}")
            state["errors"].append(f"Save error: {str(e)}")
            state["status"] = "save_failed"
        
        return state
    
    async def handle_error_node(self, state: LeadGenerationState) -> LeadGenerationState:
        """
        Error handling node
        """
        self.logger.error(f"Workflow error: {state['errors'][-1] if state['errors'] else 'Unknown error'}")
        state["status"] = "failed"
        state["completed_at"] = datetime.utcnow().isoformat()
        return state
    
    def should_continue_after_scrape(self, state: LeadGenerationState) -> str:
        """Decide next step after scraping"""
        if state["status"] == "scrape_failed":
            if len(state["errors"]) < 3:  # Max 3 retries
                return "retry"
            return "error"
        return "continue"
    
    def should_continue_after_enrich(self, state: LeadGenerationState) -> str:
        """Decide next step after enrichment"""
        if state["status"] == "enrich_failed":
            return "error"
        return "continue"
    
    def should_continue_after_score(self, state: LeadGenerationState) -> str:
        """Decide next step after scoring"""
        if state["status"] == "score_failed":
            return "error"
        return "continue"
    
    def should_continue_after_qualify(self, state: LeadGenerationState) -> str:
        """Decide next step after qualification"""
        if state["status"] == "qualify_failed":
            return "error"
        return "continue"
    
    def should_continue_after_dedupe(self, state: LeadGenerationState) -> str:
        """Decide next step after deduplication"""
        if state["status"] == "dedupe_failed":
            return "error"
        return "continue"
    
    async def run(self, campaign_id: str, query: str, sources: List[str], target_count: int) -> Dict[str, Any]:
        """
        Run the complete workflow
        """
        initial_state: LeadGenerationState = {
            "campaign_id": campaign_id,
            "query": query,
            "sources": sources,
            "target_count": target_count,
            "current_page": 1,
            "scraped_leads": [],
            "enriched_leads": [],
            "scored_leads": [],
            "qualified_leads": [],
            "deduplicated_leads": [],
            "final_leads": [],
            "errors": [],
            "status": "started",
            "started_at": datetime.utcnow().isoformat(),
            "completed_at": None
        }
        
        self.logger.info(f"Starting workflow for campaign {campaign_id}")
        
        # Run the graph
        config = {"configurable": {"thread_id": campaign_id}}
        final_state = await self.graph.ainvoke(initial_state, config=config)
        
        return {
            "campaign_id": campaign_id,
            "status": final_state["status"],
            "total_leads": len(final_state["final_leads"]),
            "errors": final_state["errors"],
            "started_at": final_state["started_at"],
            "completed_at": final_state["completed_at"]
        }


# Singleton instance
_workflow = None


def get_workflow() -> LeadGenerationGraph:
    """Get or create workflow instance"""
    global _workflow
    if _workflow is None:
        _workflow = LeadGenerationGraph()
    return _workflow


def run_lead_generation_workflow(campaign_id: str, query: str, sources: List[str], target_count: int) -> Dict[str, Any]:
    """
    Synchronous wrapper for running workflow
    (For Celery tasks)
    """
    workflow = get_workflow()
    
    # Run async in sync context
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        result = loop.run_until_complete(
            workflow.run(campaign_id, query, sources, target_count)
        )
        return result
    finally:
        loop.close()