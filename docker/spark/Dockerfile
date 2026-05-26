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

CMD ["tail", "-f", "/dev/null"]