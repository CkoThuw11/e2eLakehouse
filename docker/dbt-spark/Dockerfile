FROM python:3.11-slim

RUN apt-get update && apt-get install -y \
    git \
    libsasl2-dev \
    libsasl2-modules \
    build-essential \
    --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir \
    dbt-core==1.9.2 \
    "dbt-spark[PyHive]==1.9.2" \
    dbt-trino

WORKDIR /usr/app

COPY docker/dbt-spark/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
CMD ["--help"]