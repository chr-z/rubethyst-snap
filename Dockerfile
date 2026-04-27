FROM python:3.11-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN apt-get update \
 && apt-get install -y --no-install-recommends \
        ffmpeg \
        ca-certificates \
        curl \
        tini \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY pyproject.toml README.md LICENSE.txt ./
COPY rubethyst_snap ./rubethyst_snap

RUN pip install --upgrade pip \
 && pip install --no-cache-dir ".[api]"

RUN useradd --create-home --uid 10001 snap \
 && mkdir -p /data/downloads \
 && chown -R snap:snap /data /app

USER snap
VOLUME ["/data/downloads"]

EXPOSE 8000

ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["rubethyst-snap-api"]
