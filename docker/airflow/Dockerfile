FROM apache/airflow:2.9.3-python3.11

USER root

RUN apt-get update && apt-get install -y \
    git \
    build-essential \
    libsasl2-dev \
    libsasl2-modules \
    --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*

USER airflow

RUN pip install --no-cache-dir \
    dbt-core==1.9.2 \
    "dbt-spark[PyHive]==1.9.2" \
    dbt-trino \
    prophet \
    pandas \
    scikit-learn \
    joblib \
    boto3 \
    trino