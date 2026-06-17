# Build context: repo root (docker compose build context = .)
FROM python:3.12-slim

WORKDIR /app

COPY docker/streamlit/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Dashboard app
COPY docker/streamlit/app.py .
COPY docker/streamlit/data.py .
COPY docker/streamlit/chat.py .

# Groq agent module — shared from docker/agent/
COPY docker/agent/agent/ ./agent/

ENV TRINO_HOST=trino \
    TRINO_PORT=8080 \
    TRINO_USER=streamlit_dashboard \
    TRINO_CATALOG=iceberg \
    TRINO_SCHEMA=gold \
    MINIO_ENDPOINT=http://minio:9000 \
    MINIO_ACCESS_KEY=admin \
    MINIO_SECRET_KEY=admin123 \
    MINIO_BUCKET=warehouse

EXPOSE 8501

CMD ["streamlit", "run", "app.py", \
     "--server.port=8501", \
     "--server.address=0.0.0.0", \
     "--server.headless=true"]
