"""
Configuration Management with Dynamic Failover Support
Supports runtime changes and multiple environments
"""

from typing import List, Optional, Any, Dict
from pydantic_settings import BaseSettings
from pydantic import ConfigDict, Field, field_validator
import os
from functools import lru_cache
import json


class LLMFailoverConfig(BaseSettings):
    """LLM Failover Configuration - Dynamic runtime changes supported"""
    
    # Primary LLM (OpenAI)
    openai_api_key: Optional[str] = Field(default=None, alias="OPENAI_API_KEY")
    openai_model: str = Field(default="gpt-4-turbo-preview", alias="OPENAI_MODEL")
    openai_base_url: str = Field(default="https://api.openai.com/v1", alias="OPENAI_BASE_URL")
    
    # Fallback 1: Anthropic Claude
    anthropic_api_key: Optional[str] = Field(default=None, alias="ANTHROPIC_API_KEY")
    anthropic_model: str = Field(default="claude-3-opus-20240229", alias="ANTHROPIC_MODEL")
    
    # Fallback 2: Local LLM (Ollama/LocalAI)
    local_llm_url: Optional[str] = Field(default=None, alias="LOCAL_LLM_URL")
    local_llm_model: str = Field(default="llama-2-70b", alias="LOCAL_LLM_MODEL")
    
    # Fallback 3: Groq (Fast inference)
    groq_api_key: Optional[str] = Field(default=None, alias="GROQ_API_KEY")
    groq_model: str = Field(default="mixtral-8x7b-32768", alias="GROQ_MODEL")
    
    # Fallback 4: Hugging Face
    huggingface_api_key: Optional[str] = Field(default=None, alias="HUGGINGFACE_API_KEY")
    huggingface_model: str = Field(default="meta-llama/Llama-2-70b-chat-hf", alias="HUGGINGFACE_MODEL")
    
    # Common settings
    temperature: float = Field(default=0.3, alias="LLM_TEMPERATURE")
    max_tokens: int = Field(default=2000, alias="LLM_MAX_TOKENS")
    request_timeout: int = Field(default=30, alias="LLM_REQUEST_TIMEOUT")
    max_retries: int = Field(default=3, alias="LLM_MAX_RETRIES")
    enable_fallback: bool = Field(default=True, alias="LLM_ENABLE_FALLBACK")
    
    # Dynamic provider order (can be changed at runtime)
    provider_order: List[str] = Field(
        default=["openai", "anthropic", "groq", "local", "huggingface"],
        alias="LLM_PROVIDER_ORDER"
    )
    
    model_config = ConfigDict(
        case_sensitive=False,
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )
    
    def get_active_providers(self) -> List[Dict[str, Any]]:
        """Returns list of active LLM providers based on available API keys"""
        providers = []
        
        # Check each provider dynamically
        if self.openai_api_key:
            providers.append({
                "name": "openai",
                "api_key": self.openai_api_key,
                "model": self.openai_model,
                "base_url": self.openai_base_url,
                "priority": self.provider_order.index("openai") if "openai" in self.provider_order else 0
            })
        
        if self.anthropic_api_key:
            providers.append({
                "name": "anthropic",
                "api_key": self.anthropic_api_key,
                "model": self.anthropic_model,
                "priority": self.provider_order.index("anthropic") if "anthropic" in self.provider_order else 1
            })
        
        if self.groq_api_key:
            providers.append({
                "name": "groq",
                "api_key": self.groq_api_key,
                "model": self.groq_model,
                "priority": self.provider_order.index("groq") if "groq" in self.provider_order else 2
            })
        
        if self.local_llm_url:
            providers.append({
                "name": "local",
                "base_url": self.local_llm_url,
                "model": self.local_llm_model,
                "priority": self.provider_order.index("local") if "local" in self.provider_order else 3
            })
        
        if self.huggingface_api_key:
            providers.append({
                "name": "huggingface",
                "api_key": self.huggingface_api_key,
                "model": self.huggingface_model,
                "priority": self.provider_order.index("huggingface") if "huggingface" in self.provider_order else 4
            })
        
        # Sort by priority
        providers.sort(key=lambda x: x.get("priority", 999))
        return providers
    
    def update_provider_order(self, new_order: List[str]):
        """Dynamically update provider order at runtime"""
        self.provider_order = new_order


class Settings(BaseSettings):
    """Main Settings class with dynamic configuration support"""
    
    # Application
    app_name: str = Field(default="Lead Generation System", alias="APP_NAME")
    app_env: str = Field(default="development", alias="APP_ENV")
    app_debug: bool = Field(default=True, alias="APP_DEBUG")
    app_host: str = Field(default="0.0.0.0", alias="APP_HOST")
    app_port: int = Field(default=8000, alias="APP_PORT")
    app_version: str = Field(default="1.0.0", alias="APP_VERSION")
    
    # Security
    secret_key: str = Field(default="your-secret-key-change-me", alias="SECRET_KEY")
    algorithm: str = Field(default="HS256", alias="ALGORITHM")
    access_token_expire_minutes: int = Field(default=30, alias="ACCESS_TOKEN_EXPIRE_MINUTES")
    
    # Database
    database_url: str = Field(default="postgresql+asyncpg://localhost/leadgenn", alias="DATABASE_URL")
    database_pool_size: int = Field(default=20, alias="DATABASE_POOL_SIZE")
    database_max_overflow: int = Field(default=40, alias="DATABASE_MAX_OVERFLOW")
    database_pool_timeout: int = Field(default=30, alias="DATABASE_POOL_TIMEOUT")
    database_echo: bool = Field(default=False, alias="DATABASE_ECHO")
    
    # Redis
    redis_url: str = Field(default="redis://localhost:6379/0", alias="REDIS_URL")
    redis_password: Optional[str] = Field(default=None, alias="REDIS_PASSWORD")
    redis_max_connections: int = Field(default=50, alias="REDIS_MAX_CONNECTIONS")
    redis_socket_timeout: int = Field(default=5, alias="REDIS_SOCKET_TIMEOUT")
    
    # Celery
    celery_broker_url: str = Field(default="redis://localhost:6379/1", alias="CELERY_BROKER_URL")
    celery_result_backend: str = Field(default="redis://localhost:6379/2", alias="CELERY_RESULT_BACKEND")
    celery_task_track_started: bool = Field(default=True, alias="CELERY_TASK_TRACK_STARTED")
    celery_task_time_limit: int = Field(default=3600, alias="CELERY_TASK_TIME_LIMIT")
    celery_task_soft_time_limit: int = Field(default=3000, alias="CELERY_TASK_SOFT_TIME_LIMIT")
    celery_worker_concurrency: int = Field(default=4, alias="CELERY_WORKER_CONCURRENCY")
    celery_worker_max_tasks_per_child: int = Field(
    default=100,
    alias="CELERY_WORKER_MAX_TASKS_PER_CHILD"
)
    
    # Vector Database
    chroma_host: str = Field(default="localhost", alias="CHROMA_HOST")
    chroma_port: int = Field(default=8000, alias="CHROMA_PORT")
    chroma_persist_dir: str = Field(default="./chroma_data", alias="CHROMA_PERSIST_DIR")
    chroma_collection_name: str = Field(default="leads", alias="CHROMA_COLLECTION_NAME")
    embedding_model: str = Field(default="text-embedding-3-small", alias="EMBEDDING_MODEL")
    
    # Web Scraping
    scraping_proxy_enabled: bool = Field(default=False, alias="SCRAPING_PROXY_ENABLED")
    scraping_proxy_url: Optional[str] = Field(default=None, alias="SCRAPING_PROXY_URL")
    scraping_user_agent_rotation: bool = Field(default=True, alias="SCRAPING_USER_AGENT_ROTATION")
    scraping_request_timeout: int = Field(default=30, alias="SCRAPING_REQUEST_TIMEOUT")
    scraping_max_retries: int = Field(default=3, alias="SCRAPING_MAX_RETRIES")
    scraping_rate_limit_per_minute: int = Field(default=60, alias="SCRAPING_RATE_LIMIT_PER_MINUTE")
    scraping_concurrent_browsers: int = Field(default=5, alias="SCRAPING_CONCURRENT_BROWSERS")
    
    # LinkedIn
    linkedin_username: Optional[str] = Field(default=None, alias="LINKEDIN_USERNAME")
    linkedin_password: Optional[str] = Field(default=None, alias="LINKEDIN_PASSWORD")
    linkedin_cookie: Optional[str] = Field(default=None, alias="LINKEDIN_COOKIE")
    
    # Twitter
    twitter_bearer_token: Optional[str] = Field(default=None, alias="TWITTER_BEARER_TOKEN")
    twitter_api_key: Optional[str] = Field(default=None, alias="TWITTER_API_KEY")
    
    # Email (SendGrid)
    sendgrid_api_key: Optional[str] = Field(default=None, alias="SENDGRID_API_KEY")
    sendgrid_from_email: str = Field(default="noreply@leadgen.com", alias="SENDGRID_FROM_EMAIL")
    email_batch_size: int = Field(default=100, alias="EMAIL_BATCH_SIZE")
    email_rate_limit_per_second: int = Field(default=10, alias="EMAIL_RATE_LIMIT_PER_SECOND")
    
    # Webhook
    webhook_retry_max_attempts: int = Field(default=5, alias="WEBHOOK_RETRY_MAX_ATTEMPTS")
    webhook_retry_delay_seconds: int = Field(default=30, alias="WEBHOOK_RETRY_DELAY_SECONDS")
    webhook_timeout_seconds: int = Field(default=10, alias="WEBHOOK_TIMEOUT_SECONDS")
    
    # Rate Limiting
    rate_limit_per_user: int = Field(default=100, alias="RATE_LIMIT_PER_USER")
    rate_limit_per_ip: int = Field(default=50, alias="RATE_LIMIT_PER_IP")
    rate_limit_window_minutes: int = Field(default=1, alias="RATE_LIMIT_WINDOW_MINUTES")
    
    # Monitoring
    prometheus_enabled: bool = Field(default=True, alias="PROMETHEUS_ENABLED")
    prometheus_port: int = Field(default=9090, alias="PROMETHEUS_PORT")
    sentry_dsn: Optional[str] = Field(default=None, alias="SENTRY_DSN")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    log_json_format: bool = Field(default=False, alias="LOG_JSON_FORMAT")
    
    # Cache
    cache_ttl_seconds: int = Field(default=300, alias="CACHE_TTL_SECONDS")
    cache_max_size: int = Field(default=1000, alias="CACHE_MAX_SIZE")
    
    # Export
    export_max_rows: int = Field(default=10000, alias="EXPORT_MAX_ROWS")
    export_temp_dir: str = Field(default="/tmp/lead_exports", alias="EXPORT_TEMP_DIR")
    
    # CORS
    cors_origins: List[str] = Field(default=["http://localhost:3000", "http://localhost:8000"], alias="CORS_ORIGINS")
    allowed_hosts: List[str] = Field(default=["localhost", "127.0.0.1"], alias="ALLOWED_HOSTS")
    enable_api_key_auth: bool = Field(default=True, alias="ENABLE_API_KEY_AUTH")
    
    # Features
    enable_lead_deduplication: bool = Field(default=True, alias="ENABLE_LEAD_DEDUPLICATION")
    enable_lead_scoring: bool = Field(default=True, alias="ENABLE_LEAD_SCORING")
    enable_lead_enrichment: bool = Field(default=True, alias="ENABLE_LEAD_ENRICHMENT")
    enable_auto_email_outreach: bool = Field(default=False, alias="ENABLE_AUTO_EMAIL_OUTREACH")
    
    # LLM Failover Configuration
    llm_failover: LLMFailoverConfig = Field(default_factory=LLMFailoverConfig)
    
    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, v):
        """Parse CORS origins from string to list"""
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",")]
        return v
    
    @field_validator("allowed_hosts", mode="before")
    @classmethod
    def parse_allowed_hosts(cls, v):
        """Parse allowed hosts from string to list"""
        if isinstance(v, str):
            return [host.strip() for host in v.split(",")]
        return v
    
    def get_database_url_async(self) -> str:
        """Get async database URL"""
        return self.database_url
    
    def get_database_url_sync(self) -> str:
        """Get sync database URL (for Alembic)"""
        return self.database_url.replace("+asyncpg", "")
    
    model_config = ConfigDict(
        case_sensitive=False,
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )


# Global settings instance with caching for performance
@lru_cache()
def get_settings() -> Settings:
    """Returns cached settings instance"""
    return Settings()


# Dynamic settings update (for runtime changes)
def reload_settings():
    """Reload settings (clears cache for dynamic updates)"""
    get_settings.cache_clear()
    return get_settings()


settings = get_settings()