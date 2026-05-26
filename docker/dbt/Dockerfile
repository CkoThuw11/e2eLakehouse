FROM python:3.11-slim

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && \
    apt-get install -y --no-install-recommends build-essential default-jre curl git && \
    rm -rf /var/lib/apt/lists/*

RUN pip install --upgrade pip

# Install dbt-spark with PyHive extras (match project dbt version)
RUN pip install "dbt-spark[PyHive]==1.10.1"

# Install postgres adapter for dbt
RUN pip install "dbt-postgres==1.11.0b1"

WORKDIR /usr/app

# copy a default entrypoint script (compose may mount a local one over it)
COPY start.sh /usr/local/bin/start.sh
RUN chmod +x /usr/local/bin/start.sh

ENTRYPOINT ["/bin/sh", "/usr/local/bin/start.sh"]
CMD ["tail", "-f", "/dev/null"]
