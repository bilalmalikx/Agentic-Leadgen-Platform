.PHONY: help dev prod install test migrate docker-up docker-down clean

GREEN := \033[0;32m
NC := \033[0m

help:
	@echo '$(GREEN)Available commands:$(NC)'
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  $(GREEN)%-20s$(NC) %s\n", $$1, $$2}'

install: ## Install dependencies
	pip install -r requirements.txt
	playwright install

dev: ## Run development server
	uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

prod: ## Run production server
	gunicorn -c gunicorn_conf.py app.main:app

docker-up: ## Start Docker containers
	docker-compose up -d

docker-down: ## Stop Docker containers
	docker-compose down

docker-build: ## Build Docker images
	docker-compose build

test: ## Run tests
	pytest -v

test-cov: ## Run tests with coverage
	pytest --cov=app --cov-report=html --cov-report=term

migrate: ## Run database migrations
	alembic upgrade head

make-migration: ## Create new migration
	alembic revision --autogenerate -m "$(MSG)"

lint: ## Run linters
	flake8 app/
	mypy app/

format: ## Format code
	black app/ --line-length 100
	isort app/ --profile black

clean: ## Clean cache
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	rm -rf .pytest_cache/ .mypy_cache/ htmlcov/

celery-worker: ## Start Celery worker
	celery -A app.core.celery_app worker --loglevel=info

celery-beat: ## Start Celery beat
	celery -A app.core.celery_app beat --loglevel=info

flower: ## Start Flower monitoring
	celery -A app.core.celery_app flower --port=5555

seed: ## Seed database
	python scripts/seed_data.py

backup: ## Backup database
	./scripts/backup_db.sh

health: ## Health check
	curl -f http://localhost:8000/health || echo "Health check failed"