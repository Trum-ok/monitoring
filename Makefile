.PHONY: lint format

package ?= sdk monitor-service

lint:
	uv run ruff check $(package)
	uv run ruff format --check $(package)
	uv run ty check $(package)

format:
	uv run ruff check --fix $(package)
	uv run ruff format $(package)
