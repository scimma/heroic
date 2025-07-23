# HEROIC Development Makefile
# Automates common development tasks

# Variables
PYTHON := poetry run python
MANAGE := $(PYTHON) manage.py
DJANGO_SETTINGS := local_settings
DB_CONTAINER := heroic-db-1

# Color codes
BLUE := \033[0;34m
GREEN := \033[0;32m
YELLOW := \033[0;33m
RED := \033[0;31m
NC := \033[0m # No Color

# Default target
.DEFAULT_GOAL := help

# Help command
.PHONY: help
help:
	@echo "$(BLUE)HEROIC Development Commands$(NC)"
	@echo ""
	@echo "$(GREEN)Setup Commands:$(NC)"
	@echo "  make install          - Install dependencies with poetry"
	@echo "  make db-start         - Start PostgreSQL database container"
	@echo "  make db-stop          - Stop PostgreSQL database container"
	@echo "  make migrate          - Run Django migrations"
	@echo "  make superuser        - Create development superuser"
	@echo "  make local-settings   - Create local_settings.py file"
	@echo "  make setup            - Complete setup (install, db-start, migrate, superuser)"
	@echo ""
	@echo "$(GREEN)Development Commands:$(NC)"
	@echo "  make run              - Start Django development server"
	@echo "  make shell            - Open Django shell"
	@echo "  make test             - Run tests"
	@echo ""
	@echo "$(GREEN)Test Data Management:$(NC)"
	@echo "  make gw-setup         - Setup LIGO, Virgo, KAGRA observatories"
	@echo "  make reset-db         - Reset database (remove all entries)"
	@echo "  make reset-force      - Reset database without confirmation"
	@echo "  make fresh-gw         - Reset database and setup GW observatories"
	@echo "  make test-gw-vis      - Test GW visibility API endpoint"
	@echo ""
	@echo "$(GREEN)Database Commands:$(NC)"
	@echo "  make db-logs          - Show database container logs"
	@echo "  make db-shell         - Open PostgreSQL shell"
	@echo "  make showmigrations   - Show migration status"
	@echo ""
	@echo "$(GREEN)Cleanup Commands:$(NC)"
	@echo "  make clean            - Remove Python cache files"
	@echo "  make clean-all        - Remove cache and stop containers"

# Setup commands
.PHONY: install
install:
	@echo "$(BLUE)Installing dependencies...$(NC)"
	poetry install

.PHONY: db-start
db-start:
	@echo "$(BLUE)Starting PostgreSQL database...$(NC)"
	@if [ ! -f .env ]; then \
		echo "$(YELLOW)Creating .env file...$(NC)"; \
		echo "DB_NAME=heroic" > .env; \
		echo "DB_USER=postgres" >> .env; \
		echo "DB_PASSWORD=postgres" >> .env; \
	fi
	docker-compose up -d db
	@echo "$(GREEN)Waiting for database to be ready...$(NC)"
	@sleep 5

.PHONY: db-stop
db-stop:
	@echo "$(BLUE)Stopping PostgreSQL database...$(NC)"
	docker-compose down db

.PHONY: migrate
migrate:
	@echo "$(BLUE)Running migrations...$(NC)"
	DJANGO_SETTINGS_MODULE=$(DJANGO_SETTINGS) $(MANAGE) migrate

.PHONY: superuser
superuser:
	@echo "$(BLUE)Creating superuser...$(NC)"
	DJANGO_SETTINGS_MODULE=$(DJANGO_SETTINGS) $(PYTHON) scripts/create_dev_superuser.py

.PHONY: local-settings
local-settings:
	@echo "$(BLUE)Creating local_settings.py...$(NC)"
	@if [ -f local_settings.py ]; then \
		echo "$(YELLOW)Warning: local_settings.py already exists!$(NC)"; \
		read -p "Overwrite? (y/N): " confirm; \
		if [ "$$confirm" != "y" ] && [ "$$confirm" != "Y" ]; then \
			echo "$(BLUE)Skipping...$(NC)"; \
			exit 0; \
		fi; \
	fi
	@echo "from heroic_base.settings import *" > local_settings.py
	@echo "" >> local_settings.py
	@echo "AUTHENTICATION_BACKENDS = [" >> local_settings.py
	@echo "    'django.contrib.auth.backends.ModelBackend'," >> local_settings.py
	@echo "]" >> local_settings.py
	@echo "" >> local_settings.py
	@echo "REST_FRAMEWORK['DEFAULT_AUTHENTICATION_CLASSES'] = (" >> local_settings.py
	@echo "    'rest_framework.authentication.SessionAuthentication'," >> local_settings.py
	@echo "    'rest_framework.authentication.TokenAuthentication'," >> local_settings.py
	@echo ")" >> local_settings.py
	@echo "" >> local_settings.py
	@echo "CSRF_TRUSTED_ORIGINS = ['http://localhost:5173','http://127.0.0.1:5173','http://*']" >> local_settings.py
	@echo "CORS_ORIGIN_ALLOW_ALL = True" >> local_settings.py
	@echo "CORS_ALLOW_CREDENTIALS = True" >> local_settings.py
	@echo "$(GREEN)Created local_settings.py$(NC)"

.PHONY: setup
setup: install local-settings db-start migrate superuser
	@echo "$(GREEN)Setup complete!$(NC)"
	@echo "Run 'make run' to start the development server"

# Development commands
.PHONY: run
run:
	@echo "$(BLUE)Starting Django development server...$(NC)"
	DJANGO_SETTINGS_MODULE=$(DJANGO_SETTINGS) $(MANAGE) runserver

.PHONY: shell
shell:
	@echo "$(BLUE)Opening Django shell...$(NC)"
	DJANGO_SETTINGS_MODULE=$(DJANGO_SETTINGS) $(MANAGE) shell

.PHONY: test
test:
	@echo "$(BLUE)Running tests...$(NC)"
	DJANGO_SETTINGS_MODULE=$(DJANGO_SETTINGS) $(MANAGE) test

# Data management
.PHONY: gw-setup
gw-setup:
	@echo "$(BLUE)Setting up GW observatories...$(NC)"
	@if [ ! -f token ]; then \
		echo "$(RED)Error: token file not found. Run 'make superuser' first.$(NC)"; \
		exit 1; \
	fi
	$(PYTHON) scripts/setup_gw_observatories.py

.PHONY: reset-db
reset-db:
	@echo "$(BLUE)Resetting database...$(NC)"
	$(PYTHON) scripts/reset_database.py

.PHONY: reset-force
reset-force:
	@echo "$(BLUE)Force resetting database...$(NC)"
	$(PYTHON) scripts/reset_database.py --force

.PHONY: fresh-gw
fresh-gw: reset-force gw-setup
	@echo "$(GREEN)Fresh GW setup complete!$(NC)"

.PHONY: test-gw-vis
test-gw-vis:
	@echo "$(BLUE)Testing GW visibility API...$(NC)"
	$(PYTHON) scripts_extra/test_gw_visibility.py

# Database commands
.PHONY: db-logs
db-logs:
	@echo "$(BLUE)Database container logs:$(NC)"
	docker logs $(DB_CONTAINER) --tail 50

.PHONY: db-shell
db-shell:
	@echo "$(BLUE)Opening PostgreSQL shell...$(NC)"
	docker exec -it $(DB_CONTAINER) psql -U postgres -d heroic

.PHONY: showmigrations
showmigrations:
	@echo "$(BLUE)Migration status:$(NC)"
	DJANGO_SETTINGS_MODULE=$(DJANGO_SETTINGS) $(MANAGE) showmigrations

# Cleanup commands
.PHONY: clean
clean:
	@echo "$(BLUE)Cleaning Python cache files...$(NC)"
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name '*.pyc' -delete
	find . -type f -name '*.pyo' -delete
	find . -type f -name '*.coverage' -delete
	find . -type d -name '.pytest_cache' -exec rm -rf {} + 2>/dev/null || true

.PHONY: clean-all
clean-all: clean db-stop
	@echo "$(GREEN)Cleanup complete!$(NC)"

# Quick development cycle
.PHONY: restart
restart: db-stop db-start migrate run
	@echo "$(GREEN)Restarted with fresh database connection!$(NC)"

# Check if everything is ready
.PHONY: check
check:
	@echo "$(BLUE)Checking development environment...$(NC)"
	@echo -n "Poetry installed: "
	@command -v poetry >/dev/null 2>&1 && echo "$(GREEN)✓$(NC)" || echo "$(RED)✗$(NC)"
	@echo -n "Docker installed: "
	@command -v docker >/dev/null 2>&1 && echo "$(GREEN)✓$(NC)" || echo "$(RED)✗$(NC)"
	@echo -n "Database running: "
	@docker ps | grep -q $(DB_CONTAINER) && echo "$(GREEN)✓$(NC)" || echo "$(RED)✗$(NC)"
	@echo -n "Token file exists: "
	@test -f token && echo "$(GREEN)✓$(NC)" || echo "$(RED)✗$(NC)"
	@echo -n ".env file exists: "
	@test -f .env && echo "$(GREEN)✓$(NC)" || echo "$(RED)✗$(NC)"
	@echo -n "local_settings.py exists: "
	@test -f local_settings.py && echo "$(GREEN)✓$(NC)" || echo "$(RED)✗$(NC)"
