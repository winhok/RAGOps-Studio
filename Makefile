.PHONY: test eval api web docker

test:
	cd backend && PYTHONPATH=. python -m unittest discover -s tests -v

eval:
	python backend/scripts/seed_and_eval.py

api:
	cd backend && PYTHONPATH=. uvicorn app.main:app --reload --port 8000

web:
	cd frontend && npm run dev

docker:
	docker compose up --build
