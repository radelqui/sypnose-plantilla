# origen: rag-banking-agent@c7e5f54
.PHONY: install test lint run dev
install: ; pip install -r requirements-dev.txt
test:    ; pytest --cov=app --cov-fail-under=85
lint:    ; ruff check . && bandit -r app -ll
dev:     ; uvicorn app.main:app --reload
run:     ; uvicorn app.main:app --host 0.0.0.0 --port 8000
