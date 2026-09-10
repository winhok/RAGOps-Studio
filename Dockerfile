FROM python:3.13-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 HOST=0.0.0.0 PORT=8000
COPY backend/requirements.txt /app/backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt \
    && useradd --create-home --uid 10001 ragops
COPY backend /app/backend
COPY scripts /app/scripts
COPY data /app/data
COPY frontend/dist /app/frontend/dist
RUN mkdir -p /app/.state /app/.secrets && chown -R ragops:ragops /app
USER ragops
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=3)"
CMD ["python", "scripts/serve.py"]
