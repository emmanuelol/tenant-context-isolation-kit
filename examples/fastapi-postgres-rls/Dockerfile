# ==============================================================================
# FastAPI + PostgreSQL Row-Level Security (RLS) Reference Demo Dockerfile
# ==============================================================================
FROM python:3.11-slim AS runtime

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install tenant-context-isolation-kit library
COPY pyproject.toml ./
COPY src/ ./src/
RUN pip install --no-cache-dir .

# Install demo dependencies
COPY examples/fastapi-postgres-rls/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy demo application
COPY examples/fastapi-postgres-rls/app.py ./app.py

EXPOSE 8000
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
