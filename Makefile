.PHONY: help dev prod install test migrate upgrade downgrade clean docker-up docker-down docker-build lint format backup restore health

# Colors for output
GREEN := \033[0;32m
RED := \033[0;31m
NC := \033[0m # No Color

help: ## Show this help message
	@echo '$(GREEN)Available commands:$(NC)'
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  $(GREEN)%-20s$(NC) %s\n", $$1, $$2}'

install: ## Install dependencies
	@echo "$(GREEN)Installing dependencies...$(NC)"
	poetry install
	poetry run playwright install

dev: ## Run development server with hot reload
	@echo "$(GREEN)Starting development server...$(NC)"
	poetry run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

prod: ## Run production server (with multiple workers)
	@echo "$(GREEN)Starting production server...$(NC)"
	poetry run gunicorn app.main:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000

docker-up: ## Start all containers with Docker Compose
	@echo "$(GREEN)Starting Docker containers...$(NC)"
	docker-compose up -d

docker-down: ## Stop all containers
	@echo "$(GREEN)Stopping Docker containers...$(NC)"
	docker-compose down

docker-build: ## Build Docker images
	@echo "$(GREEN)Building Docker images...$(NC)"
	docker-compose build

docker-logs: ## View Docker logs
	docker-compose logs -f

test: ## Run tests
	@echo "$(GREEN)Running tests...$(NC)"
	poetry run pytest -v

test-cov: ## Run tests with coverage
	@echo "$(GREEN)Running tests with coverage...$(NC)"
	poetry run pytest --cov=app --cov-report=html --cov-report=term

test-integration: ## Run integration tests
	@echo "$(GREEN)Running integration tests...$(NC)"
	poetry run pytest tests/integration -v

migrate: ## Run database migrations
	@echo "$(GREEN)Running migrations...$(NC)"
	poetry run alembic upgrade head

upgrade: ## Upgrade database to latest migration
	@echo "$(GREEN)Upgrading database...$(NC)"
	poetry run alembic upgrade +1

downgrade: ## Downgrade database by one migration
	@echo "$(GREEN)Downgrading database...$(NC)"
	poetry run alembic downgrade -1

make-migration: ## Create new migration (MSG="migration message")
	@echo "$(GREEN)Creating migration: $(MSG)...$(NC)"
	poetry run alembic revision --autogenerate -m "$(MSG)"

lint: ## Run linters
	@echo "$(GREEN)Running linters...$(NC)"
	poetry run flake8 app/
	poetry run mypy app/

format: ## Format code with black and isort
	@echo "$(GREEN)Formatting code...$(NC)"
	poetry run black app/
	poetry run isort app/

clean: ## Clean cache and temporary files
	@echo "$(GREEN)Cleaning cache...$(NC)"
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	find . -type f -name ".coverage" -delete
	rm -rf .pytest_cache/ .mypy_cache/ .ruff_cache/ htmlcov/ dist/ build/ *.egg-info/

backup: ## Backup database
	@echo "$(GREEN)Backing up database...$(NC)"
	./scripts/backup_db.sh

restore: ## Restore database from backup
	@echo "$(GREEN)Restoring database...$(NC)"
	./scripts/restore_db.sh

health: ## Check system health
	@echo "$(GREEN)Checking health...$(NC)"
	curl -f http://localhost:8000/health || echo "$(RED)Health check failed$(NC)"

celery-worker: ## Start Celery worker
	@echo "$(GREEN)Starting Celery worker...$(NC)"
	poetry run celery -A app.core.celery_app worker --loglevel=info

celery-beat: ## Start Celery beat scheduler
	@echo "$(GREEN)Starting Celery beat...$(NC)"
	poetry run celery -A app.core.celery_app beat --loglevel=info

flower: ## Start Flower monitoring for Celery
	@echo "$(GREEN)Starting Flower...$(NC)"
	poetry run celery -A app.core.celery_app flower --port=5555

seed: ## Seed database with demo data
	@echo "$(GREEN)Seeding database...$(NC)"
	poetry run python scripts/seed_data.py

logs: ## View application logs
	tail -f logs/app.log 2>/dev/null || echo "No logs found. Run 'mkdir logs' first."

shell: ## Open Python shell with app context
	poetry run python -c "import app; from app.core.database import SessionLocal; db = SessionLocal(); print('Shell ready. db session available as `db`')" || poetry run ipython