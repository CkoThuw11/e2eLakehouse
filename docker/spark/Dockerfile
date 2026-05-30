FROM apache/spark:3.5.1

USER root

ENV SPARK_HOME=/opt/spark
ENV PATH=$SPARK_HOME/bin:$PATH

RUN mkdir -p /opt/spark-app

COPY docker/spark/download_jars.sh /opt/download_jars.sh

RUN sed -i 's/\r$//' /opt/download_jars.sh && \
    chmod +x /opt/download_jars.sh && \
    /opt/download_jars.sh

WORKDIR /opt/spark-app

CMD ["tail", "-f", "/dev/null"]