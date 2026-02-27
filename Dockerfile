FROM python:3.11-slim

LABEL maintainer="MCUB-fork"
LABEL description="MCUB (Mitrich Cube UserBot) - Telegram UserBot"

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

RUN pip install --no-cache-dir \
    aiohttp-jinja2 \
    jinja2 \
    Pillow

COPY core/ ./core/
COPY modules/ ./modules/
COPY utils/ ./utils/
COPY core_inline/ ./core_inline/
COPY img/ ./img/
COPY version.txt .
COPY repositories.json .

RUN mkdir -p /app/data

ENV MCUB_NO_WEB=0
ENV MCUB_PORT=8080
ENV MCUB_HOST=0.0.0.0

EXPOSE 8080

CMD ["python", "-m", "core"]
