#!/bin/bash

mkdir -p /opt/spark/jars

cd /opt/spark/jars

echo "Downloading Iceberg runtime..."
wget -nc https://repo1.maven.org/maven2/org/apache/iceberg/iceberg-spark-runtime-3.5_2.12/1.5.2/iceberg-spark-runtime-3.5_2.12-1.5.2.jar

echo "Downloading Hadoop AWS..."
wget -nc https://repo1.maven.org/maven2/org/apache/hadoop/hadoop-aws/3.3.4/hadoop-aws-3.3.4.jar

echo "Downloading AWS SDK..."
wget -nc https://repo1.maven.org/maven2/com/amazonaws/aws-java-sdk-bundle/1.12.262/aws-java-sdk-bundle-1.12.262.jar

echo "Downloading PostgreSQL JDBC..."
wget -nc https://repo1.maven.org/maven2/org/postgresql/postgresql/42.7.3/postgresql-42.7.3.jar

echo "All jars downloaded successfully."