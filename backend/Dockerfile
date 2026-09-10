FROM python:3.12-slim
WORKDIR /workspace
COPY backend/requirements.txt /workspace/backend/requirements.txt
RUN pip install --no-cache-dir -r /workspace/backend/requirements.txt
COPY backend /workspace/backend
COPY data /workspace/data
ENV PYTHONPATH=/workspace/backend
ENV RAGOPS_DB_PATH=/workspace/data/ragops.db
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--app-dir", "/workspace/backend", "--host", "0.0.0.0", "--port", "8000"]
