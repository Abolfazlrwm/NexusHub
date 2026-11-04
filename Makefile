.PHONY: help install install-api test test-api lint lint-all typecheck typecheck-api check run-api

help:  ## Show available tasks
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033%-16s\033 %s\n", $$1, $$2}'

install:  ## Install engine dev dependencies
	pip install -e "packages/nexusagent[dev]"

install-api:  ## Install engine + gateway dev dependencies
	pip install -e "packages/nexusagent[dev]" -e "apps/api[dev]"

test:  ## Run the engine test suite
	cd packages/nexusagent && pytest -q

test-api:  ## Run the gateway test suite
	cd apps/api && pytest -q

lint:  ## Lint the engine with ruff
	ruff check packages/nexusagent

lint-all:  ## Lint engine and gateway with ruff
	ruff check packages/nexusagent apps/api

typecheck:  ## Type-check the engine with mypy
	cd packages/nexusagent && mypy src

typecheck-api:  ## Type-check the gateway with mypy
	cd apps/api && mypy src

check: lint typecheck test  ## Run all engine checks (lint + types + tests)

check-all: lint-all typecheck typecheck-api test test-api  ## Run every check in the monorepo

run-api:  ## Start the gateway locally (http://127.0.0.1:8000)
	uvicorn nexushub_api.main:app --reload --port 8000
