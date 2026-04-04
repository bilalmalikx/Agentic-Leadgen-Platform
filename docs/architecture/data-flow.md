
```markdown
# Data Flow Documentation

## Lead Generation Data Flow

### 1. Campaign Creation Flow
User Request
│
▼
POST /api/v1/campaigns
│
▼
Input Validation (Guardrails)
│
▼
Create Campaign Record (PostgreSQL)
│
▼
Trigger Celery Task (generate_leads_task)
│
▼
Return Campaign ID (202 Accepted)

text

### 2. Lead Generation Workflow
┌─────────────────────────────────────────────────────────────────────────────┐
│ LangGraph Workflow │
├─────────────────────────────────────────────────────────────────────────────┤
│ │
│ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ │
│ │ Scrape │───▶│ Enrich │───▶│ Score │───▶│ Qualify │ │
│ │ Leads │ │ Leads │ │ Leads │ │ Leads │ │
│ └────┬─────┘ └──────────┘ └──────────┘ └────┬─────┘ │
│ │ │ │
│ ▼ ▼ │
│ ┌──────────┐ ┌──────────┐ │
│ │ Validate │◀───────────────────────────────────│Deduplicate│ │
│ │ Leads │ │ Leads │ │
│ └────┬─────┘ └────┬─────┘ │
│ │ │ │
│ └──────────────────┬───────────────────────────┘ │
│ │ │
│ ▼ │
│ ┌──────────┐ │
│ │ Save │ │
│ │ Leads │ │
│ └──────────┘ │
└─────────────────────────────────────────────────────────────────────────────┘

text

### 3. Detailed Node Operations

#### Node 1: Scrape Leads
Input: query, sources, limit
Process:
x
For each source (parallel):

LinkedIn: Playwright scraping

Twitter: API + Playwright

Crunchbase: HTTP requests

Extract profile data

Store raw_data JSON
Output: List of scraped leads

text

#### Node 2: Validate Leads
Input: scraped leads
Process:

Email format validation

Phone number validation

URL validation

Data completeness check
Output: Validated leads (invalid filtered out)

text

#### Node 3: Enrich Leads
Input: validated leads
Process:

For each lead:

Build enrichment prompt

Call LLM (with failover)

Parse JSON response

Add enriched fields:

company_size

funding_stage

tech_stack

industry
Output: Enriched leads

text

#### Node 4: Score Leads
Input: enriched leads
Process:

Calculate component scores:

job_title_match (30%)

company_relevance (25%)

social_activity (20%)

company_size (15%)

location_match (10%)

Apply weights

Blend with AI score (optional)

Determine quality (hot/warm/cold)
Output: Scored leads (0-100)

text

#### Node 5: Qualify Leads
Input: scored leads
Process:

RAG retrieval:

Find similar qualified leads

Calculate similarity scores

LLM qualification:

Compare with examples

Generate reasoning

Rule-based fallback
Output: Qualified/Rejected leads

text

#### Node 6: Deduplicate Leads
Input: qualified leads
Process:

Exact email matching

Fuzzy name matching

Vector similarity search

Mark duplicates
Output: Unique leads

text

#### Node 7: Save Leads
Input: deduplicated leads
Process:

Insert into PostgreSQL

Generate embeddings

Store in ChromaDB

Trigger webhook (async)
Output: Saved leads

text

### 4. Database Schema Relationships
┌─────────────┐ ┌─────────────┐ ┌─────────────┐
│ User │────▶│ Campaign │────▶│ Lead │
└─────────────┘ └─────────────┘ └─────────────┘
│ │
│ │
▼ ▼
┌─────────────┐ ┌─────────────┐
│ScrapingJob │ │ EmailLog │
└─────────────┘ └─────────────┘

text

### 5. API Request/Response Flow
Client
│
│ POST /api/v1/campaigns
▼
API Gateway (Nginx)
│
│ Rate Limiting Check
▼
FastAPI Middleware
│
│ Authentication (JWT/API Key)
│ Request ID Generation
│ Logging
▼
Route Handler (campaigns.py)
│
│ Input Validation
│ Create DB Record
│ Trigger Celery Task
▼
Response (202 Accepted)
│
│ Campaign ID
▼
Client

text

### 6. Async Processing Flow
API Request
│
▼
Celery Task Queued
│
├──▶ high_priority queue
│
▼
Celery Worker
│
├──▶ Acquire task
├──▶ Process (LangGraph)
├──▶ Update database
├──▶ Send webhook
│
▼
Task Complete

text

### 7. Webhook Flow
Event Trigger
│
▼
Webhook Service
│
├──▶ Create delivery record
├──▶ Generate signature
├──▶ Send HTTP request
│
├──▶ Success → Update status
│
└──▶ Failure → Schedule retry
│
▼
Exponential Backoff
(30s, 60s, 120s, 240s, 480s)

text

### 8. Error Handling Flow
Error Occurred
│
▼
┌──────────────────────────────────────┐
│ Error Handler │
├──────────────────────────────────────┤
│ 1. Log error with traceback │
│ 2. Determine error type │
│ 3. Map to HTTP status code │
│ 4. Format response │
│ 5. Return to client │
└──────────────────────────────────────┘

text

### 9. Data Retention Flow
Daily Cleanup Job (2 AM)
│
▼
Cleanup Tasks
│
├──▶ Soft delete leads > 90 days
├──▶ Delete failed scraping jobs > 7 days
├──▶ Clean old export files > 24 hours
└──▶ Reset user quotas (monthly)

text

### 10. Cache Flow
Request
│
▼
Check Cache (Redis)
│
├──▶ HIT → Return cached data
│
└──▶ MISS → Fetch from DB
│
▼
Store in Cache
│
▼
Return to Client

text

**📝 File Explanation (3 Lines):**
1. **Purpose:** Complete data flow documentation - campaign creation, lead generation workflow, error handling
2. **Functions:** Understanding system behavior, debugging, onboarding new developers
3. **Usage:** Reference for understanding how data moves through the system

