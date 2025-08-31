.PHONY: setup run dev test index lint fmt api docs

setup:
	poetry install --no-root
	cp -n .env.example .env || true

run:
	poetry run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

dev: run

test:
	poetry run pytest -q

index:
	poetry run python scripts/index_kb.py

lint:
	poetry run ruff check app

fmt:
	poetry run black app && poetry run isort app

docs:
	@echo "Open http://localhost:8000/docs"
