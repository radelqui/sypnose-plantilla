.PHONY: install test lint dev run

SERVICE_NAME ?= {{SERVICE_NAME}}
SERVICE_PORT ?= {{SERVICE_PORT}}

install:
	pip install -e ".[dev]"

test:
	python -m pytest tests/ -v --tb=short

lint:
	ruff check app/ tests/
	ruff format --check app/ tests/

dev:
	uvicorn app.main:app --host 0.0.0.0 --port $(SERVICE_PORT) --reload

run:
	uvicorn app.main:app --host 0.0.0.0 --port $(SERVICE_PORT)
