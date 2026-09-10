.PHONY: install bootstrap serve test web
install:
	python -m pip install -r backend/requirements-dev.txt
bootstrap:
	python scripts/bootstrap.py --with-sample-data
serve:
	python scripts/serve.py
test:
	python -m pytest -q
web:
	npm run build --prefix frontend
