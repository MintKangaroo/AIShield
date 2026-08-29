.PHONY: install lint format format-check typecheck test schema-check web-install web-check web-test compose-check check

install:
	python -m pip install -e ".[dev,ml]"

lint:
	python -m ruff check .

format:
	python -m ruff format .

format-check:
	python -m ruff format --check .

typecheck:
	python -m mypy .

test:
	python -m pytest

schema-check:
	python -m aishield.schemas.export --check schemas/experiment-result.schema.json

web-install:
	npm --prefix web ci

web-check:
	npm --prefix web run check

web-test:
	npm --prefix web run test

compose-check:
	docker compose config --quiet
	docker compose --profile gpu config --quiet

check: lint format-check typecheck test schema-check
