FROM apache/spark:3.5.1

USER root

ENV SPARK_HOME=/opt/spark
ENV PATH=$SPARK_HOME/bin:$PATH

RUN mkdir -p /opt/spark-app

# copy download script and application sources from repo (build context is project root)
COPY docker/spark/download_jars.sh /opt/download_jars.sh
COPY docker/spark/spark-app /opt/spark-app
COPY docker/spark/spark-config /opt/bitnami/spark/conf
COPY docker/spark/spark-config/core-site.xml /opt/spark/conf/core-site.xml
COPY docker/spark/spark-config/hive-site.xml /opt/spark/conf/hive-site.xml

RUN sed -i 's/\r$//' /opt/download_jars.sh && \
    chmod +x /opt/download_jars.sh && \
    /opt/download_jars.sh

WORKDIR /opt/spark-app

# Install python/pip and dbt so this image can also be used for dbt tasks
USER root
RUN apt-get update \
    && apt-get install -y python3 python3-pip git ca-certificates --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*

RUN python3 -m pip install --no-cache-dir dbt-core dbt-postgres "dbt-spark[PyHive]" || true

# Create a small wrapper and start script for running dbt inside the container
RUN printf '%s\n' "#!/usr/bin/env python3" "import os,sys" "os.environ.setdefault('DBT_PROFILES_DIR','/usr/app')" "os.environ.setdefault('DBT_PROJECT_DIR','/usr/app')" "from dbt.cli.main import cli" "sys.argv=['dbt']+sys.argv[1:]" "cli()" > /usr/local/bin/dbt_wrapper.py \
    && chmod +x /usr/local/bin/dbt_wrapper.py

# expose a simple 'debug' command so running `docker exec -it <container> debug` works
RUN printf '%s\n' "#!/bin/sh" "exec python3 /usr/local/bin/dbt_wrapper.py debug \"\$@\"" > /usr/local/bin/debug \
    && chmod +x /usr/local/bin/debug

RUN printf '%s\n' "#!/bin/sh" "set -e" "# Run dbt debug against mounted project" "python3 /usr/local/bin/dbt_wrapper.py debug || true" "tail -f /dev/null" > /usr/local/bin/start_dbt.sh \
    && chmod +x /usr/local/bin/start_dbt.sh

CMD ["tail", "-f", "/dev/null"]