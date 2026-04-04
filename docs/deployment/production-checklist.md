# 🚀 Production Deployment Checklist

---

## 🧩 1. Pre-Deployment Checklist

### 🔧 Environment Configuration

* [ ] `.env.production` configured
* [ ] `APP_ENV=production`
* [ ] `APP_DEBUG=false`
* [ ] Strong `SECRET_KEY`
* [ ] Secure DB credentials
* [ ] Redis password configured
* [ ] API keys rotated (LLMs, email services)

---

### 🔐 Security

* [ ] HTTPS enabled (SSL certificates)
* [ ] CORS restricted
* [ ] Allowed hosts configured
* [ ] Rate limiting enabled
* [ ] API authentication (JWT/API Keys)
* [ ] PII masking enabled
* [ ] Audit logs enabled

---

### 🗄️ Database (PostgreSQL)

* [ ] PostgreSQL 15+ installed
* [ ] Connection pooling enabled
* [ ] Daily backups configured
* [ ] Read replicas (if needed)
* [ ] Migrations tested
* [ ] Indexes optimized

---

### ⚡ Redis

* [ ] Redis 7+ installed
* [ ] Password secured
* [ ] Memory limits set
* [ ] Persistence enabled (AOF/RDB)
* [ ] Connection limits configured

---

### 🧠 Vector DB (ChromaDB)

* [ ] Service running
* [ ] Persistent storage configured
* [ ] Collections initialized
* [ ] Backup strategy defined

---

### 🖥️ Application

* [ ] Dependencies installed
* [ ] Playwright configured
* [ ] Gunicorn setup (`workers = CPU * 2 + 1`)
* [ ] Logging & rotation configured
* [ ] Health endpoints working

---

### 📊 Monitoring

* [ ] Prometheus configured
* [ ] Grafana dashboards ready
* [ ] Loki logging enabled
* [ ] Alerts configured
* [ ] (Optional) Sentry integrated

---

### 🐳 Docker (Optional)

* [ ] Images built
* [ ] Production compose file ready
* [ ] Persistent volumes configured
* [ ] Resource limits applied
* [ ] Restart policies enabled

---

### 🌐 Load Balancer (Nginx)

* [ ] SSL configured
* [ ] Rate limiting enabled
* [ ] Upstreams configured
* [ ] Health checks enabled
* [ ] Access logs enabled

---

### 💾 Backup Strategy

* [ ] Daily DB backups
* [ ] Redis backups
* [ ] File storage backups (S3/MinIO)
* [ ] Retention ≥ 30 days
* [ ] Restore tested

---

## 🚀 2. Deployment Steps

### Step 1: Setup Environment

```bash
git clone https://github.com/yourorg/lead-generation-system.git
cd lead-generation-system

cp .env.example .env.production
```

---

### Step 2: Install Dependencies

```bash
pip install -r requirements.txt
# OR
poetry install --no-dev
```

---

### Step 3: Run Migrations

```bash
alembic upgrade head
python scripts/seed_data.py
```

---

### Step 4: Start Services

#### 🐳 Option A: Docker

```bash
docker-compose -f docker-compose.prod.yml up -d
docker-compose -f docker-compose.prod.yml logs -f
```

#### ⚙️ Option B: System Services

```bash
systemctl start leadgen-api
systemctl start leadgen-worker
systemctl start leadgen-celery-beat
```

---

### Step 5: Verify Deployment

```bash
curl https://yourdomain.com/health
curl https://yourdomain.com/metrics
```

---

## 🧪 3. Post-Deployment Checks

### ✅ Monitoring

* Prometheus targets UP
* Grafana dashboards active
* Logs flowing (Loki)
* Alerts working

---

### ⚡ Performance

* API latency < 200ms
* Workers processing correctly
* DB connections stable

---

### 🔐 Security

* Run vulnerability scan
* Validate auth flows
* Check rate limits

---

## 🎯 Summary

* Production-ready deployment flow
* Covers security, scaling, monitoring
* Designed for reliability & fault tolerance

---
