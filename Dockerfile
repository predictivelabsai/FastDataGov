FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PORT=5062

WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends curl ca-certificates \
    && apt-get clean && rm -rf /var/lib/apt/lists/*
COPY pyproject.toml README.md LICENSE requirements.txt ./
COPY fastdatagov ./fastdatagov
RUN pip install --no-cache-dir ".[snowflake]"
COPY static ./static
COPY main.py docker-entrypoint.sh ./
RUN chmod +x docker-entrypoint.sh
RUN groupadd --system fastdatagov && useradd --system --gid fastdatagov --home-dir /app --no-create-home fastdatagov \
    && chown -R fastdatagov:fastdatagov /app

USER fastdatagov

EXPOSE 5062
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:5062/healthz').read()"

ENTRYPOINT ["./docker-entrypoint.sh"]
CMD ["python", "main.py"]
