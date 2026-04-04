# Lead Generation System

AI-powered lead generation system with guardrails, MCP tools, and production-ready architecture.

## Features

- 🔍 **Multi-source Web Scraping** - LinkedIn, Twitter, Crunchbase, Company Websites
- 🤖 **AI-Powered Enrichment** - GPT-4o, Claude, Groq with auto-failover
- 📊 **Lead Scoring & Qualification** - RAG-based intelligent qualification
- 🔄 **Async Task Processing** - Celery with Redis broker
- 🛡️ **Guardrails** - PII detection, toxicity filter, compliance checker
- 📦 **Vector Database** - ChromaDB for semantic search
- 🚀 **Production Ready** - Docker, monitoring, health checks

## Tech Stack

- **Framework**: FastAPI
- **Database**: PostgreSQL + SQLAlchemy
- **Cache/Queue**: Redis + Celery
- **AI**: LangChain + LangGraph + OpenAI/Anthropic/Groq
- **Vector DB**: ChromaDB
- **Scraping**: Playwright
- **Container**: Docker + Docker Compose

## Quick Start

### Prerequisites

- Python 3.9+
- PostgreSQL 15+
- Redis 7+
- Docker (optional)

### Installation

```bash
# Clone repository
git clone https://github.com/yourusername/lead-generation-system.git
cd lead-generation-system

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Install Playwright browsers
playwright install

# Copy environment variables
cp .env.example .env
# Edit .env with your API keys

# Run database migrations
alembic upgrade head

# Run the app
python run.py