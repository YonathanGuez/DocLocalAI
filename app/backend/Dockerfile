FROM registry.access.redhat.com/ubi9/python-311:latest AS base

WORKDIR /opt/app-root/src
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ ./app/
COPY scripts/ ./scripts/

# --- test stage: base + dev deps + tests, never shipped to prod ---
FROM base AS test

COPY requirements-dev.txt .
RUN pip install --no-cache-dir -r requirements-dev.txt

COPY pytest.ini .
COPY tests/ ./tests/

CMD ["python3", "-m", "pytest", "-v"]

# --- prod stage: default build target, lean runtime image ---
FROM base AS prod

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
