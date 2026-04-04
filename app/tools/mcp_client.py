"""
MCP Client - Model Context Protocol Client
For calling external MCP tools and integrating with other AI systems
"""

from typing import Dict, Any, List, Optional
import httpx
import json
from datetime import datetime

from app.core.logging import get_logger
from app.core.config import settings

logger = get_logger(__name__)


class MCPClient:
    """
    MCP Client for calling external MCP servers
    Can integrate with Claude Desktop, Cursor, or other MCP-compatible tools
    """
    
    def __init__(self, server_url: Optional[str] = None):
        self.server_url = server_url or "http://localhost:8000/mcp"
        self.client = httpx.AsyncClient(timeout=30.0)
    
    async def call_tool(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
        request_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Call a tool on an MCP server
        
        Args:
            tool_name: Name of the tool to call
            arguments: Tool arguments
            request_id: Optional request ID (generated if not provided)
        
        Returns:
            Tool response
        """
        if not request_id:
            from uuid import uuid4
            request_id = str(uuid4())
        
        request = {
            "id": request_id,
            "tool": tool_name,
            "arguments": arguments
        }
        
        logger.info(f"MCP Client: Calling tool '{tool_name}' with args {arguments}")
        
        try:
            response = await self.client.post(
                self.server_url,
                json=request
            )
            
            if response.status_code != 200:
                return {
                    "success": False,
                    "error": f"HTTP {response.status_code}: {response.text}",
                    "request_id": request_id
                }
            
            result = response.json()
            
            logger.info(f"MCP Client: Tool '{tool_name}' returned {result.get('result', {}).get('success', False)}")
            return result
            
        except Exception as e:
            logger.error(f"MCP Client failed to call tool '{tool_name}': {e}")
            return {
                "success": False,
                "error": str(e),
                "request_id": request_id
            }
    
    async def get_tools_list(self) -> List[Dict[str, Any]]:
        """
        Get list of available tools from MCP server
        """
        try:
            response = await self.client.get(f"{self.server_url}/tools")
            
            if response.status_code == 200:
                data = response.json()
                return data.get("tools", [])
            else:
                logger.error(f"Failed to get tools list: {response.status_code}")
                return []
                
        except Exception as e:
            logger.error(f"Failed to get tools list: {e}")
            return []
    
    async def get_server_info(self) -> Dict[str, Any]:
        """
        Get MCP server information
        """
        try:
            response = await self.client.get(f"{self.server_url}/info")
            
            if response.status_code == 200:
                return response.json()
            else:
                return {"error": f"HTTP {response.status_code}"}
                
        except Exception as e:
            return {"error": str(e)}
    
    async def scrape_linkedin(self, query: str, limit: int = 50) -> Dict[str, Any]:
        """Convenience method to scrape LinkedIn"""
        return await self.call_tool(
            tool_name="scrape_linkedin",
            arguments={"query": query, "limit": limit}
        )
    
    async def enrich_lead(
        self,
        email: str,
        company_name: Optional[str] = None,
        job_title: Optional[str] = None
    ) -> Dict[str, Any]:
        """Convenience method to enrich a lead"""
        arguments = {"email": email}
        if company_name:
            arguments["company_name"] = company_name
        if job_title:
            arguments["job_title"] = job_title
        
        return await self.call_tool(
            tool_name="enrich_lead",
            arguments=arguments
        )
    
    async def score_lead(
        self,
        lead_id: Optional[str] = None,
        email: Optional[str] = None
    ) -> Dict[str, Any]:
        """Convenience method to score a lead"""
        arguments = {}
        if lead_id:
            arguments["lead_id"] = lead_id
        if email:
            arguments["email"] = email
        
        return await self.call_tool(
            tool_name="score_lead",
            arguments=arguments
        )
    
    async def search_leads(
        self,
        query: str,
        status: Optional[str] = None,
        limit: int = 20
    ) -> Dict[str, Any]:
        """Convenience method to search leads"""
        arguments = {"query": query, "limit": limit}
        if status:
            arguments["status"] = status
        
        return await self.call_tool(
            tool_name="search_leads",
            arguments=arguments
        )
    
    async def get_campaign_status(self, campaign_id: str) -> Dict[str, Any]:
        """Convenience method to get campaign status"""
        return await self.call_tool(
            tool_name="get_campaign_status",
            arguments={"campaign_id": campaign_id}
        )
    
    async def export_leads(self, campaign_id: str, format: str = "csv") -> Dict[str, Any]:
        """Convenience method to export leads"""
        return await self.call_tool(
            tool_name="export_leads",
            arguments={"campaign_id": campaign_id, "format": format}
        )
    
    async def create_campaign(
        self,
        name: str,
        query: str,
        sources: List[str],
        target_leads: int = 100
    ) -> Dict[str, Any]:
        """Convenience method to create a campaign"""
        return await self.call_tool(
            tool_name="create_campaign",
            arguments={
                "name": name,
                "query": query,
                "sources": sources,
                "target_leads": target_leads
            }
        )
    
    async def close(self):
        """Close HTTP client"""
        await self.client.aclose()


# Singleton instance
_mcp_client = None


def get_mcp_client() -> MCPClient:
    """Get or create MCP client instance"""
    global _mcp_client
    if _mcp_client is None:
        _mcp_client = MCPClient()
    return _mcp_client


# Example usage for Claude Desktop integration
def get_claude_desktop_config() -> Dict[str, Any]:
    """
    Generate Claude Desktop configuration for this MCP server
    """
    return {
        "mcpServers": {
            "lead-generation": {
                "command": "python",
                "args": ["-m", "app.tools.mcp_server"],
                "env": {
                    "PYTHONPATH": "."
                }
            }
        }
    }


# FastAPI endpoint for external MCP clients
from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/mcp-client", tags=["MCP Client"])


@router.post("/call")
async def call_external_tool(
    server_url: str,
    tool_name: str,
    arguments: Dict[str, Any]
):
    """
    Call a tool on an external MCP server
    """
    client = MCPClient(server_url=server_url)
    result = await client.call_tool(tool_name, arguments)
    await client.close()
    return result