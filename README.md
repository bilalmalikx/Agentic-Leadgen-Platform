# 🚀 Lead Generation System

<p align="center">
  <b>AI-powered Lead Generation Platform with Agentic Workflows, Guardrails & Production-Ready Architecture</b>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/FastAPI-Backend-green?style=for-the-badge&logo=fastapi">
  <img src="https://img.shields.io/badge/Celery-Async-orange?style=for-the-badge&logo=celery">
  <img src="https://img.shields.io/badge/Redis-Cache-red?style=for-the-badge&logo=redis">
  <img src="https://img.shields.io/badge/PostgreSQL-DB-blue?style=for-the-badge&logo=postgresql">
  <img src="https://img.shields.io/badge/AI-LangGraph-purple?style=for-the-badge">
</p>

---

## 🧩 Overview

An **AI-powered lead generation system** that automates:

* 🔍 Lead discovery from multiple sources
* 🤖 AI enrichment using LLMs
* 📊 Intelligent scoring & qualification
* 🔄 Async processing at scale
* 🛡️ Guardrails for safe AI execution

---

## ✨ Features

### 🔍 Multi-source Data Collection

* LinkedIn scraping (Playwright)
* Twitter/X extraction
* Crunchbase & company websites
* Parallel scraping pipelines

---

### 🤖 AI-Powered Enrichment

* GPT-4o / Claude / Groq integration
* Auto failover between providers
* Structured JSON outputs
* Context-aware enrichment

---

### 📊 Lead Scoring & Qualification

* Weighted scoring system
* RAG-based similarity matching
* AI reasoning + rule fallback
* Hot / Warm / Cold classification

---

### ⚡ Async Processing

* Celery workers with Redis broker
* Distributed task queues
* High throughput processing
* Fault-tolerant execution

---

### 🛡️ AI Guardrails

* PII detection
* Toxicity filtering
* Compliance validation
* Output sanitization

---

### 📦 Vector Intelligence

* ChromaDB integration
* Semantic search
* Duplicate detection
* Embedding-based matching

---

### 🚀 Production Ready

* Dockerized services
* Health checks
* Monitoring ready
* Scalable architecture

---

## 🏗️ Architecture

```text
Client → Nginx → FastAPI → Celery → LangGraph → DB + Vector Store
```

* **FastAPI** → API Layer
* **Celery** → Background Processing
* **LangGraph** → AI Workflow Orchestration
* **Redis** → Cache + Queue
* **PostgreSQL** → Primary DB
* **ChromaDB** → Vector Search

---

## 🛠️ Tech Stack

| Layer       | Technology                |
| ----------- | ------------------------- |
| Backend     | FastAPI                   |
| Database    | PostgreSQL + SQLAlchemy   |
| Cache/Queue | Redis + Celery            |
| AI          | LangChain + LangGraph     |
| LLMs        | OpenAI / Anthropic / Groq |
| Vector DB   | ChromaDB                  |
| Scraping    | Playwright                |
| DevOps      | Docker + Compose          |

---

## ⚡ Quick Start

### 📋 Prerequisites

* Python 3.9+
* PostgreSQL 15+
* Redis 7+
* Docker (optional)

---

### 🚀 Installation

```bash
# Clone repository
git clone https://github.com/bilalmalikx/Agentic-Leadgen-Platform
cd lead-generation-system

# Create virtual environment
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Install Playwright browsers
playwright install

# Setup environment
cp .env.example .env
```

---

### ⚙️ Configuration

Update `.env`:

```env
DATABASE_URL=postgresql://user:password@localhost/db
REDIS_URL=redis://localhost:6379
OPENAI_API_KEY=your_key
```

---

### 🗄️ Database Setup

```bash
alembic upgrade head
```

---

### ▶️ Run Application

```bash
python run.py
```

---

## 📡 API Example

```bash
curl -X POST http://localhost:8000/api/v1/campaigns \
  -H "Authorization: Bearer TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name":"Test Campaign","query":"AI startups","sources":["linkedin"]}'
```

---

## 📊 System Flow

```text
Create Campaign → Queue Task → Scrape → Enrich → Score → Qualify → Store → Notify
```

---

## 📁 Project Structure

```text
app/
 ├── api/
 ├── services/
 ├── agents/
 ├── workers/
 ├── core/
 └── models/

scripts/
docker/
infra/
```

---

## 📈 Monitoring (Optional)

* Prometheus → Metrics
* Grafana → Dashboards
* Loki → Logs
* AlertManager → Alerts

---

## 🛡️ Security

* JWT Authentication
* Rate Limiting
* Guardrails (PII + Toxicity)
* Audit Logging

---

## 🚀 Deployment

See:

* 📄 Deployment Checklist
* 📄 Data Flow Documentation
* 📄 Architecture Document

---

## 🧠 Why This Project?

This project demonstrates:

* ✅ Agentic AI system design
* ✅ Scalable backend architecture
* ✅ Async distributed processing
* ✅ Real-world production patterns

---

## 👨‍💻 Author

**Bilal Malik**
AI Engineer | Agentic Systems Developer

---

## ⭐ Star This Repo

If you found this useful, consider giving it a ⭐

---
