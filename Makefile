.PHONY: lint format fix

fix:
	ruff check --fix .
	ruff format .

lint:
	ruff check .

format:
	ruff format .
