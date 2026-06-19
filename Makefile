install:
	.venv/bin/python -m pip install -e ".[dev]"

run:
	.venv/bin/python -m uvicorn travel_scrapping.main:app --host 127.0.0.1 --port 8000

search:
	.venv/bin/python -m travel_scrapping.cli search

test:
	.venv/bin/python -m pytest

coverage:
	.venv/bin/python -m pytest --cov --cov-report=term-missing
