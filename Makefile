.PHONY: lint format migrate dev

package ?= sdk monitor-service
host ?= 127.0.0.1
port ?= 8000

lint:
	uv run ruff check $(package)
	uv run ruff format --check $(package)
	uv run isort --check-only $(package)
	uv run ty check $(package)

format:
	uv run ruff check --fix $(package)
	uv run ruff format $(package)
	uv run isort $(package)

migrate:
	cd monitor-service && uv run alembic upgrade head

dev:
	cd monitor-service && uv run uvicorn main:app --reload --host $(host) --port $(port)
