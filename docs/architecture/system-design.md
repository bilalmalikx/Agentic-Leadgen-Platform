# 🚀 Lead Generation System – System Design Document

---

## 🧩 1. System Overview

The **Lead Generation System** is an AI-powered platform designed to:

* Automatically discover leads from multiple sources
* Enrich data using LLMs
* Score and qualify leads intelligently
* Remove duplicates using vector similarity

---

## 🏗️ 2. High-Level Architecture

```text
                ┌───────────────────────────────┐
                │         Client Layer          │
                │ Web | API | MCP | Webhooks    │
                └──────────────┬────────────────┘
                               │
                               ▼
                ┌───────────────────────────────┐
                │     Load Balancer (Nginx)     │
                └──────────────┬────────────────┘
                               │
                               ▼
                ┌───────────────────────────────┐
                │      API Gateway (FastAPI)    │
                └──────────────┬────────────────┘
                               │
        ┌──────────────────────┼──────────────────────┐
        ▼                      ▼                      ▼
┌───────────────┐     ┌───────────────┐     ┌───────────────┐
│ Service Layer │     │ Worker Layer  │     │ Cache Layer   │
│               │     │ (Celery)      │     │ (Redis)       │
└──────┬────────┘     └──────┬────────┘     └───────────────┘
       │                     │
       ▼                     ▼
        ┌────────────────────────────────────────────┐
        │               Data Layer                   │
        │ PostgreSQL | ChromaDB | Redis | S3         │
        └────────────────────────────────────────────┘
```

---

## ⚙️ 3. Component Breakdown

### 🔹 3.1 API Layer (FastAPI)

**Responsibilities:**

* Handle incoming requests
* Validate data
* Authenticate users

**Key Features:**

* Async processing
* Middleware (Auth, Rate Limit, Logging)
* OpenAPI documentation
* Dependency Injection

---

### 🤖 3.2 Agent Layer (LangGraph)

**Purpose:** AI workflow orchestration

**Agents:**

| Agent                 | Responsibility      |
| --------------------- | ------------------- |
| LeadScraperAgent      | Scrape leads        |
| LeadEnricherAgent     | Enrich using LLM    |
| LeadScorerAgent       | Score (0–100)       |
| LeadQualifierAgent    | RAG-based filtering |
| LeadDeduplicatorAgent | Remove duplicates   |

---

### ⚡ 3.3 Worker Layer (Celery)

**Purpose:** Async background processing

**Queues:**

* `high_priority` → Critical tasks
* `scraping` → Data collection
* `email` → Email delivery
* `low_priority` → Cleanup jobs

---

### 🗄️ 3.4 Data Layer

| Technology | Role          |
| ---------- | ------------- |
| PostgreSQL | Primary DB    |
| Redis      | Cache + Queue |
| ChromaDB   | Vector search |
| S3 / MinIO | File storage  |

---

## 🔄 4. Data Flow

```text
User Request
     │
     ▼
API Validation
     │
     ▼
Database Entry
     │
     ▼
Celery Task Trigger
     │
     ▼
LangGraph Workflow

1. Scrape Data
2. Enrich via LLM
3. Score Leads
4. Qualify (RAG)
5. Deduplicate
6. Store Results

     ▼
Webhook → External Systems
```

---

## 🔐 5. Security Architecture

| Layer            | Description    |
| ---------------- | -------------- |
| Input Validation | Guardrails     |
| Authentication   | JWT + API Keys |
| Rate Limiting    | IP/User based  |
| Authorization    | RBAC           |
| Output Filtering | PII masking    |
| Logging          | Audit trails   |

---

## 📈 6. Scaling Strategy

| Component | Strategy             |
| --------- | -------------------- |
| API       | Horizontal scaling   |
| Workers   | Scale Celery workers |
| Database  | Read replicas        |
| Cache     | Redis Cluster        |
| Vector DB | Distributed setup    |

---

## 🚀 7. Deployment Architecture

```text
Production Setup:

- API Servers: x3
- Workers: x5
- Redis: Cache + Broker
- PostgreSQL: Primary DB
- ChromaDB: Vector DB

Infra:
- Nginx
- Prometheus
- Grafana
```

---

## 📊 8. Monitoring Stack

* Metrics → Prometheus
* Dashboards → Grafana
* Logs → Loki + Promtail
* Tracing → Tempo
* Alerts → AlertManager

---

## 🛑 9. Disaster Recovery

| Scenario        | RTO    | RPO    | Solution         |
| --------------- | ------ | ------ | ---------------- |
| DB Failure      | 15 min | 5 min  | Backup + Replica |
| Region Failure  | 1 hour | 15 min | Multi-region     |
| Data Corruption | 30 min | 24 hr  | PITR             |

---

## 🎯 10. Why This Architecture?

* ✅ Scalable (Horizontal scaling)
* ✅ Async processing (Celery)
* ✅ AI orchestration (LangGraph)
* ✅ Clean separation of concerns
* ✅ Production-ready

---

## 🧠 Interview Explanation (Short)

> "This system uses FastAPI for async APIs, Celery for background processing, and LangGraph for AI workflows.
> It scales horizontally, uses Redis for caching, and ChromaDB for vector similarity — making it production-ready and efficient."

---

## 📌 Usage

* Portfolio Project
* System Design Interviews
* Production Blueprint

---
