.PHONY: install dev test probe lint

install:
	python3.11 -m venv .venv || python3 -m venv .venv
	.venv/bin/pip install -U pip
	.venv/bin/pip install -r requirements.txt
	cd frontend && npm install

dev:
	@echo "Starting API on :8000 (frontend Vite on :5173 in another terminal: make frontend)"
	.venv/bin/uvicorn backend.api:app --reload --host 0.0.0.0 --port 8000

frontend:
	cd frontend && npm run dev

test:
	.venv/bin/pytest -q

probe:
	.venv/bin/python scripts/probes/run_all.py
