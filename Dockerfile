# OrgMemBench harness image. The harness runs in this container; each memory
# system under test runs as its own service (see docker/ + docker-compose.yml).
FROM python:3.11-slim

WORKDIR /app

# System deps kept minimal; per-adapter extras are installed via pip extras.
RUN apt-get update && apt-get install -y --no-install-recommends git curl \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md ./
COPY orgmembench ./orgmembench
# Install core; add extras per the systems you intend to run, e.g.:
#   pip install -e '.[mem0,zep]'
RUN pip install --no-cache-dir -e .

COPY datasets ./datasets
COPY config ./config
COPY tests ./tests

# Dry-run by default; flip to 0 (and provide keys) for a real run.
ENV ORGMEMBENCH_DRY_RUN=1

ENTRYPOINT ["orgmembench"]
CMD ["--help"]
