.PHONY: help install test lint typecheck check

help:  ## Show available tasks
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'

install:  ## Install engine dev dependencies
	pip install -e "packages/nexusagent[dev]"

test:  ## Run the engine test suite
	cd packages/nexusagent && pytest -q

lint:  ## Lint with ruff
	ruff check packages/nexusagent

typecheck:  ## Type-check with mypy
	cd packages/nexusagent && mypy src

check: lint typecheck test  ## Run all checks (lint + types + tests)
