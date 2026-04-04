# Data Flow Documentation

## Lead Generation Data Flow

### 1. Campaign Creation Flow

### 2. Lead Generation Workflow

---

## **147. docs/deployment/production-checklist.md**

```markdown
# Production Deployment Checklist

## Pre-Deployment Checklist

### 1. Environment Configuration
- [ ] `.env.production` file created with all variables
- [ ] `APP_ENV=production` set
- [ ] `APP_DEBUG=false` set
- [ ] `SECRET_KEY` changed from default (strong random key)
- [ ] Database credentials are strong
- [ ] Redis password set
- [ ] API keys rotated (OpenAI, SendGrid, etc.)

### 2. Security
- [ ] HTTPS/SSL configured (Let's Encrypt or paid cert)
- [ ] CORS origins restricted to your domains
- [ ] Allowed hosts configured
- [ ] Rate limits configured appropriately
- [ ] API key authentication enabled
- [ ] PII detection enabled
- [ ] Audit logging enabled

### 3. Database
- [ ] PostgreSQL 15+ installed
- [ ] Connection pooling configured
- [ ] Backups configured (daily)
- [ ] Read replica configured (if high traffic)
- [ ] Migrations tested
- [ ] Indexes created for performance

### 4. Redis
- [ ] Redis 7+ installed
- [ ] Password configured
- [ ] Max memory limit set
- [ ] Persistence enabled (AOF or RDB)
- [ ] Connection limit configured

### 5. Vector Database (ChromaDB)
- [ ] ChromaDB service running
- [ ] Persistent volume configured
- [ ] Collection created
- [ ] Backup strategy in place

### 6. Application
- [ ] All Python dependencies installed
- [ ] Playwright browsers installed
- [ ] Gunicorn configured (workers = CPU * 2 + 1)
- [ ] Log rotation configured
- [ ] Health check endpoints working

### 7. Monitoring
- [ ] Prometheus configured
- [ ] Grafana dashboards imported
- [ ] Loki for log aggregation
- [ ] Alerts configured (Slack/PagerDuty)
- [ ] Sentry for error tracking (optional)

### 8. Docker (if using containers)
- [ ] Images built and tagged
- [ ] Docker Compose production file ready
- [ ] Volumes configured for persistence
- [ ] Resource limits set (CPU, memory)
- [ ] Restart policies configured

### 9. Load Balancer (Nginx)
- [ ] SSL certificates installed
- [ ] Rate limiting configured
- [ ] Upstream servers configured
- [ ] Health checks enabled
- [ ] Logging configured

### 10. Backup Strategy
- [ ] Database backups scheduled (daily)
- [ ] Redis backups configured
- [ ] Export files backup (if using S3)
- [ ] Backup retention policy (30 days minimum)
- [ ] Backup restoration tested

## Deployment Steps

### Step 1: Prepare Environment
```bash
# Clone repository
git clone https://github.com/yourorg/lead-generation-system.git
cd lead-generation-system

# Copy production environment
cp .env.example .env.production
# Edit .env.production with production values