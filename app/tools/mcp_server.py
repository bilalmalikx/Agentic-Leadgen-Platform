"""
MCP Server - Model Context Protocol Server
Exposes tools for AI assistants (Claude, GPT, etc.) to interact with the system
"""

from typing import Dict, Any, List, Optional
import json
import asyncio
from datetime import datetime
from uuid import UUID

from app.core.logging import get_logger
from app.core.config import settings
from app.tools.mcp_tools import (
    scrape_linkedin_tool,
    enrich_lead_tool,
    score_lead_tool,
    search_leads_tool,
    get_campaign_status_tool,
    export_leads_tool
)

logger = get_logger(__name__)


class MCPServer:
    """
    Model Context Protocol Server
    Provides a standardized interface for AI assistants to call tools
    """
    
    def __init__(self):
        self.tools = self._register_tools()
        self.server_name = "lead-generation-mcp"
        self.server_version = "1.0.0"
    
    def _register_tools(self) -> Dict[str, Dict[str, Any]]:
        """
        Register all available tools with their schemas
        """
        return {
            "scrape_linkedin": {
                "function": scrape_linkedin_tool,
                "description": "Scrape LinkedIn profiles based on search query",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Search query for LinkedIn (e.g., 'CTO at AI startup')"
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Maximum number of profiles to scrape",
                            "default": 50
                        }
                    },
                    "required": ["query"]
                }
            },
            "enrich_lead": {
                "function": enrich_lead_tool,
                "description": "Enrich lead data using AI (company info, funding, tech stack)",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "email": {
                            "type": "string",
                            "description": "Lead email address"
                        },
                        "company_name": {
                            "type": "string",
                            "description": "Company name"
                        },
                        "job_title": {
                            "type": "string",
                            "description": "Job title"
                        }
                    },
                    "required": ["email"]
                }
            },
            "score_lead": {
                "function": score_lead_tool,
                "description": "Score a lead based on multiple criteria (0-100)",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "lead_id": {
                            "type": "string",
                            "description": "Lead ID (UUID)"
                        },
                        "email": {
                            "type": "string",
                            "description": "Lead email"
                        }
                    },
                    "required": []
                }
            },
            "search_leads": {
                "function": search_leads_tool,
                "description": "Search leads in the database",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Search query"
                        },
                        "status": {
                            "type": "string",
                            "enum": ["new", "contacted", "qualified", "converted", "rejected"],
                            "description": "Filter by status"
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Maximum results",
                            "default": 20
                        }
                    },
                    "required": ["query"]
                }
            },
            "get_campaign_status": {
                "function": get_campaign_status_tool,
                "description": "Get status and progress of a campaign",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "campaign_id": {
                            "type": "string",
                            "description": "Campaign ID (UUID)"
                        }
                    },
                    "required": ["campaign_id"]
                }
            },
            "export_leads": {
                "function": export_leads_tool,
                "description": "Export leads to CSV or JSON format",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "campaign_id": {
                            "type": "string",
                            "description": "Campaign ID to export from"
                        },
                        "format": {
                            "type": "string",
                            "enum": ["csv", "json"],
                            "description": "Export format",
                            "default": "csv"
                        }
                    },
                    "required": ["campaign_id"]
                }
            }
        }
    
    async def handle_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle incoming MCP request
        """
        request_id = request.get("id")
        tool_name = request.get("tool")
        arguments = request.get("arguments", {})
        
        logger.info(f"MCP request: tool={tool_name}, args={arguments}")
        
        try:
            # Validate tool exists
            if tool_name not in self.tools:
                return {
                    "id": request_id,
                    "error": {
                        "code": -32601,
                        "message": f"Tool not found: {tool_name}"
                    }
                }
            
            # Get tool function
            tool = self.tools[tool_name]
            tool_function = tool["function"]
            
            # Execute tool
            result = await tool_function(**arguments)
            
            # Return success response
            return {
                "id": request_id,
                "result": result
            }
            
        except Exception as e:
            logger.error(f"MCP request failed: {e}")
            return {
                "id": request_id,
                "error": {
                    "code": -32000,
                    "message": str(e)
                }
            }
    
    def get_tools_list(self) -> List[Dict[str, Any]]:
        """
        Get list of all available tools with their schemas
        For AI assistants to discover available tools
        """
        tools_list = []
        
        for name, tool in self.tools.items():
            tools_list.append({
                "name": name,
                "description": tool["description"],
                "parameters": tool["parameters"]
            })
        
        return tools_list
    
    def get_server_info(self) -> Dict[str, Any]:
        """
        Get server information
        """
        return {
            "name": self.server_name,
            "version": self.server_version,
            "tools_count": len(self.tools),
            "tools": self.get_tools_list()
        }


# Singleton instance
_mcp_server = None


def get_mcp_server() -> MCPServer:
    """Get or create MCP server instance"""
    global _mcp_server
    if _mcp_server is None:
        _mcp_server = MCPServer()
    return _mcp_server


# FastAPI endpoint for MCP
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/mcp", tags=["MCP"])


class MCPRequest(BaseModel):
    """MCP request model"""
    id: str
    tool: str
    arguments: Dict[str, Any] = {}


class MCPResponse(BaseModel):
    """MCP response model"""
    id: str
    result: Optional[Any] = None
    error: Optional[Dict[str, Any]] = None


@router.post("/", response_model=MCPResponse)
async def mcp_endpoint(request: MCPRequest):
    """
    MCP endpoint for AI assistants to call tools
    """
    server = get_mcp_server()
    result = await server.handle_request(request.dict())
    return MCPResponse(**result)


@router.get("/tools")
async def list_tools():
    """
    List all available MCP tools
    """
    server = get_mcp_server()
    return {"tools": server.get_tools_list()}


@router.get("/info")
async def server_info():
    """
    Get MCP server information
    """
    server = get_mcp_server()
    return server.get_server_info()