"""
LLM Client with Failover Support
Dynamically switches between multiple LLM providers
"""

from typing import List, Dict, Any, Optional
import asyncio
import json
from openai import AsyncOpenAI
from anthropic import AsyncAnthropic
import httpx

from app.core.logging import get_logger
from app.core.config import settings

logger = get_logger(__name__)


class LLMClientWithFailover:
    """
    LLM client that automatically fails over to backup providers
    Supports: OpenAI, Anthropic, Groq, Local LLM, HuggingFace
    """
    
    def __init__(self):
        self.providers = []
        self._init_providers()
    
    def _init_providers(self):
        """Initialize all available providers based on config"""
        config = settings.llm_failover
        active_providers = config.get_active_providers()
        
        for provider in active_providers:
            name = provider.get("name")
            
            if name == "openai":
                self.providers.append({
                    "name": "openai",
                    "client": AsyncOpenAI(
                        api_key=provider.get("api_key"),
                        base_url=provider.get("base_url"),
                        timeout=config.request_timeout
                    ),
                    "model": provider.get("model"),
                    "priority": provider.get("priority", 0)
                })
            
            elif name == "anthropic":
                self.providers.append({
                    "name": "anthropic",
                    "client": AsyncAnthropic(
                        api_key=provider.get("api_key"),
                        timeout=config.request_timeout
                    ),
                    "model": provider.get("model"),
                    "priority": provider.get("priority", 1)
                })
            
            elif name == "groq":
                self.providers.append({
                    "name": "groq",
                    "client": AsyncOpenAI(
                        api_key=provider.get("api_key"),
                        base_url="https://api.groq.com/openai/v1",
                        timeout=config.request_timeout
                    ),
                    "model": provider.get("model"),
                    "priority": provider.get("priority", 2)
                })
            
            elif name == "local":
                self.providers.append({
                    "name": "local",
                    "client": AsyncOpenAI(
                        base_url=provider.get("base_url"),
                        timeout=config.request_timeout
                    ),
                    "model": provider.get("model"),
                    "priority": provider.get("priority", 3)
                })
            
            elif name == "huggingface":
                self.providers.append({
                    "name": "huggingface",
                    "client": None,  # Will use HTTP client
                    "base_url": "https://api-inference.huggingface.co/models",
                    "model": provider.get("model"),
                    "api_key": provider.get("api_key"),
                    "priority": provider.get("priority", 4)
                })
        
        # Sort by priority
        self.providers.sort(key=lambda x: x.get("priority", 999))
        
        logger.info(f"Initialized {len(self.providers)} LLM providers: {[p['name'] for p in self.providers]}")
    
    async def complete(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.3,
        max_tokens: int = 2000,
        retry_count: int = 0
    ) -> str:
        """
        Get completion from LLM with automatic failover
        """
        for idx, provider in enumerate(self.providers):
            try:
                logger.debug(f"Trying provider: {provider['name']}")
                
                if provider["name"] == "huggingface":
                    response = await self._call_huggingface(provider, prompt)
                else:
                    response = await self._call_openai_compatible(provider, prompt, system_prompt, temperature, max_tokens)
                
                logger.info(f"Successfully used provider: {provider['name']}")
                return response
                
            except Exception as e:
                logger.warning(f"Provider {provider['name']} failed: {e}")
                
                if idx == len(self.providers) - 1:
                    # Last provider failed
                    if retry_count < settings.llm_failover.max_retries:
                        logger.info(f"Retrying with all providers (attempt {retry_count + 1})")
                        await asyncio.sleep(2 ** retry_count)
                        return await self.complete(prompt, system_prompt, temperature, max_tokens, retry_count + 1)
                    else:
                        raise Exception(f"All LLM providers failed after {retry_count} retries")
        
        raise Exception("No LLM providers available")
    
    async def _call_openai_compatible(
        self,
        provider: Dict[str, Any],
        prompt: str,
        system_prompt: Optional[str],
        temperature: float,
        max_tokens: int
    ) -> str:
        """
        Call OpenAI-compatible API
        """
        messages = []
        
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        
        messages.append({"role": "user", "content": prompt})
        
        client = provider["client"]
        model = provider["model"]
        
        response = await client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens
        )
        
        return response.choices[0].message.content
    
    async def _call_huggingface(self, provider: Dict[str, Any], prompt: str) -> str:
        """
        Call HuggingFace Inference API
        """
        url = f"{provider['base_url']}/{provider['model']}"
        headers = {"Authorization": f"Bearer {provider['api_key']}"}
        
        async with httpx.AsyncClient(timeout=settings.llm_failover.request_timeout) as client:
            response = await client.post(
                url,
                headers=headers,
                json={
                    "inputs": prompt,
                    "parameters": {
                        "max_new_tokens": 500,
                        "temperature": 0.3
                    }
                }
            )
            
            if response.status_code != 200:
                raise Exception(f"HuggingFace API error: {response.status_code}")
            
            result = response.json()
            
            # HuggingFace returns list of generated text
            if isinstance(result, list) and len(result) > 0:
                return result[0].get("generated_text", "")
            
            return str(result)
    
    async def complete_with_json(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.2
    ) -> Dict[str, Any]:
        """
        Get JSON response from LLM
        """
        enhanced_system = (system_prompt or "") + "\n\nRespond with valid JSON only. No other text."
        
        response = await self.complete(
            prompt=prompt,
            system_prompt=enhanced_system,
            temperature=temperature
        )
        
        # Parse JSON response
        response = response.strip()
        
        # Remove markdown code blocks
        if response.startswith("```json"):
            response = response[7:]
        if response.startswith("```"):
            response = response[3:]
        if response.endswith("```"):
            response = response[:-3]
        
        try:
            return json.loads(response)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON response: {e}")
            return {"error": "Invalid JSON response", "raw_response": response[:500]}


# Singleton instance
_llm_client = None


def get_llm_client() -> LLMClientWithFailover:
    """Get or create LLM client instance"""
    global _llm_client
    if _llm_client is None:
        _llm_client = LLMClientWithFailover()
    return _llm_client