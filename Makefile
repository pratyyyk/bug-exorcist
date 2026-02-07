.PHONY: setup-backend setup-frontend dev-backend dev-frontend lint-backend test-backend lint-frontend build-frontend

setup-backend:
	cd backend && python -m pip install -r requirements.txt && python -m pip install -r requirements-dev.txt

setup-frontend:
	cd frontend && npm ci

dev-backend:
	cd backend && python -m uvicorn app.main:app --reload

dev-frontend:
	cd frontend && npm run dev

lint-backend:
	ruff check . && black --check . && mypy .

test-backend:
	python -m pytest -q

lint-frontend:
	cd frontend && npm run lint

build-frontend:
	cd frontend && npm run build
