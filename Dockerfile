FROM python:3.12-slim

LABEL maintainer="MCUB-fork"
LABEL description="MCUB (Mitrich UserBot) - Telegram UserBot"

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/*

RUN git clone --depth 1 https://github.com/hairpin01/MCUB-fork.git .

RUN pip install --no-cache-dir -r requirements.txt

RUN mkdir -p /app/data

ENV MCUB_NO_WEB=0
ENV MCUB_PORT=8081
ENV MCUB_HOST=0.0.0.0

EXPOSE 8081

CMD ["python", "-m", "core"]
