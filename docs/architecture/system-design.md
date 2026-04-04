# 🔄 Data Flow Documentation – Lead Generation System

---

## 🧩 1. Campaign Creation Flow

```text
User Request
    │
    ▼
POST /api/v1/campaigns
    │
    ▼
Validation (Guardrails)
    │
    ▼
Create Campaign (PostgreSQL)
    │
    ▼
Trigger Celery Task
    │
    ▼
Response → 202 Accepted (Campaign ID)
```

---

## 🤖 2. Lead Generation Workflow (LangGraph)

```text
Scrape → Validate → Enrich → Score → Qualify → Deduplicate → Save
```

---

## ⚙️ 3. Node-Level Processing

### 🔹 Scrape Leads

* Multi-source scraping (LinkedIn, Twitter, etc.)
* Uses Playwright + APIs
* Outputs raw JSON

---

### 🔹 Validate Leads

* Email, phone, URL validation
* Removes incomplete records

---

### 🔹 Enrich Leads

* LLM-based enrichment
* Adds:

  * Company size
  * Industry
  * Tech stack
  * Funding stage

---

### 🔹 Score Leads

* Weighted scoring system:

| Factor        | Weight |
| ------------- | ------ |
| Job Title     | 30%    |
| Company Match | 25%    |
| Activity      | 20%    |
| Company Size  | 15%    |
| Location      | 10%    |

---

### 🔹 Qualify Leads

* RAG-based similarity matching
* LLM reasoning
* Rule fallback

---

### 🔹 Deduplicate

* Email matching
* Fuzzy name matching
* Vector similarity

---

### 🔹 Save Leads

* Store in PostgreSQL
* Generate embeddings
* Store in ChromaDB
* Trigger webhook

---

## 🗄️ 4. Data Relationships

```text
User → Campaign → Lead
        │
        ├── ScrapingJob
        └── EmailLog
```

---

## 🌐 5. API Flow

```text
Client → Nginx → FastAPI
        │
        ├─ Auth (JWT/API Key)
        ├─ Rate Limit
        ├─ Logging
        ▼
Route Handler → DB → Celery
        ▼
Response → Client
```

---

## ⚡ 6. Async Processing

```text
API → Queue → Worker → Process → DB → Webhook
```

---

## 🔗 7. Webhook Flow

```text
Trigger Event
    │
    ▼
Webhook Service
    │
    ├─ Send Request
    ├─ Success → Update
    └─ Failure → Retry

Retry Strategy:
30s → 60s → 120s → 240s → 480s
```

---

## ❌ 8. Error Handling

```text
Error → Log → Classify → Map Status → Respond
```

---

## 🧹 9. Data Retention

* Leads > 90 days → soft delete
* Failed jobs > 7 days → delete
* Exports > 24h → cleanup
* Monthly → quota reset

---

## ⚡ 10. Cache Flow

```text
Request → Redis
   │
   ├─ HIT → Return
   └─ MISS → DB → Cache → Return
```

---

## 🎯 Summary

* End-to-end system data movement
* Covers sync + async flows
* Includes validation, AI processing, storage

---

## 🧠 Interview Explanation

> "Data flows from API to Celery workers, processed via LangGraph pipeline (scrape → enrich → score → qualify), then stored in DB and vector store, with caching and webhook notifications."

---
