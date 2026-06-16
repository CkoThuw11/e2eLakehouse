FROM apache/airflow:2.9.3-python3.11

USER root

RUN apt-get update && apt-get install -y \
    git \
    build-essential \
    libsasl2-dev \
    libsasl2-modules \
    openjdk-17-jre-headless \
    wget \
    procps \
    docker.io \            
    --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*

ENV JAVA_HOME=/usr/lib/jvm/java-17-openjdk-amd64

ARG DOCKER_GID=989
RUN groupadd -f -g ${DOCKER_GID} docker && usermod -aG docker airflow  

USER airflow

RUN pip install --no-cache-dir \
    dbt-core==1.9.2 \
    "dbt-spark[PyHive]==1.9.2" \
    dbt-trino \
    pyspark==3.5.1 \
    prophet \
    pandas \
    scikit-learn \
    joblib \
    boto3 \
    trino

ENV SPARK_HOME=/home/airflow/.local/lib/python3.11/site-packages/pyspark
ENV PATH=$SPARK_HOME/bin:/home/airflow/.local/bin:$PATH

RUN cd $SPARK_HOME/jars && \
    wget -nc https://repo1.maven.org/maven2/org/apache/iceberg/iceberg-spark-runtime-3.5_2.12/1.5.2/iceberg-spark-runtime-3.5_2.12-1.5.2.jar && \
    wget -nc https://repo1.maven.org/maven2/org/apache/hadoop/hadoop-aws/3.3.4/hadoop-aws-3.3.4.jar && \
    wget -nc https://repo1.maven.org/maven2/com/amazonaws/aws-java-sdk-bundle/1.12.262/aws-java-sdk-bundle-1.12.262.jar && \
    wget -nc https://repo1.maven.org/maven2/org/postgresql/postgresql/42.7.3/postgresql-42.7.3.jar