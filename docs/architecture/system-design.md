# System Design Document

## Lead Generation System - Architecture Overview

### 1. System Overview

The Lead Generation System is an AI-powered platform that automatically discovers, enriches, scores, and qualifies leads from multiple sources.


### 3. Component Details

#### 3.1 API Layer (FastAPI)

- **Purpose**: Handle HTTP requests, authentication, rate limiting
- **Key Features**:
  - Async request handling
  - Automatic OpenAPI documentation
  - Dependency injection
  - Middleware support (CORS, logging, auth)

#### 3.2 Agent Layer (LangGraph)

- **Purpose**: Orchestrate AI-powered lead processing
- **Agents**:
  - `LeadScraperAgent`: Multi-source web scraping
  - `LeadEnricherAgent`: AI-powered data enrichment
  - `LeadScorerAgent`: Lead scoring algorithm
  - `LeadQualifierAgent`: RAG-based qualification
  - `LeadDeduplicatorAgent`: Duplicate detection

#### 3.3 Worker Layer (Celery)

- **Purpose**: Background task processing
- **Task Queues**:
  - `high_priority`: Critical tasks (lead generation)
  - `scraping`: Web scraping tasks
  - `email`: Email delivery
  - `low_priority`: Cleanup and maintenance

#### 3.4 Data Layer

| Technology | Purpose |
|------------|---------|
| PostgreSQL | Primary database, ACID compliance |
| Redis | Caching, session storage, Celery broker |
| ChromaDB | Vector storage for semantic search |
| S3/MinIO | Export file storage |


### 6. Scaling Strategy

| Component | Scaling Method |
|-----------|----------------|
| API | Horizontal (multiple replicas) |
| Workers | Horizontal (multiple Celery workers) |
| Database | Read replicas + connection pooling |
| Cache | Redis Cluster |
| Vector DB | ChromaDB clustering |

### 7. Deployment Architecture

### 8. Monitoring Stack

- **Metrics**: Prometheus
- **Visualization**: Grafana
- **Logs**: Loki + Promtail
- **Traces**: Tempo
- **Alerts**: AlertManager

### 9. Disaster Recovery

| Scenario | RTO | RPO | Strategy |
|----------|-----|-----|----------|
| Database failure | 15 min | 5 min | Automated backups, read replica |
| Region failure | 1 hour | 15 min | Multi-region replication |
| Data corruption | 30 min | 24 hours | Point-in-time recovery |

