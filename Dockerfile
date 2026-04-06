# Multi-stage Dockerfile for MCUB-fork
# Builder prepares dependencies without polluting runtime image.

FROM python:3.12-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# System deps needed to compile binary wheels (e.g., cryptg)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libffi-dev \
    && rm -rf /var/lib/apt/lists/*

# Install runtime dependencies into an isolated prefix we can copy later
COPY requirements.txt ./
RUN python -m pip install --upgrade pip \
    && pip install --no-cache-dir --prefix /install -r requirements.txt

# --- Runtime image ---
FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    MCUB_NO_WEB=0 \
    MCUB_PORT=8081 \
    MCUB_HOST=0.0.0.0

# Create non-root user for safer execution
RUN addgroup --system mcub && adduser --system --ingroup mcub mcub

WORKDIR /app

# Copy python deps from builder
COPY --from=builder /install /usr/local

# Copy source code last to maximise layer cache
COPY . .

USER mcub
EXPOSE 8081

CMD ["python", "-m", "core"]
