from pyspark.sql import SparkSession
from pyspark.sql.functions import lit
import os


def main():

    pg_host = os.getenv("NORTHWIND_DB_HOST", "northwind-db")
    pg_port = os.getenv("NORTHWIND_DB_PORT", "5432")
    pg_db   = os.getenv("NORTHWIND_DB_NAME", "northwind")
    pg_user = os.getenv("NORTHWIND_DB_USER", "admin")
    pg_pwd  = os.getenv("NORTHWIND_DB_PASSWORD", "admin")

    jdbc_url = f"jdbc:postgresql://{pg_host}:{pg_port}/{pg_db}"

    props = {
        "user": pg_user,
        "password": pg_pwd,
        "driver": "org.postgresql.Driver"
    }

    spark = (
        SparkSession.builder
        .appName("Bronze Ingestion (Option A - Hive Iceberg)")
        .enableHiveSupport()
        .config("spark.sql.extensions",
                "org.apache.iceberg.spark.extensions.IcebergSparkSessionExtensions")
        .config("spark.sql.catalog.lakehouse",
                "org.apache.iceberg.spark.SparkCatalog")
        .config("spark.sql.catalog.lakehouse.type", "hive")
        .config("spark.sql.catalog.lakehouse.uri", "thrift://hive-metastore:9083")
        .config("spark.sql.catalog.lakehouse.warehouse", "s3a://warehouse/")
        .config("spark.sql.defaultCatalog", "lakehouse")
        .getOrCreate()
    )

    tables = ["categories", "customers", "employees", "orders","order_details", "products", "suppliers"]


    for t in tables:

        print(f"Processing {t}")

        df = spark.read.jdbc(jdbc_url, t, properties=props)

        target = f"bronze.{t}"


        df.writeTo(target).overwrite(lit(True))

        print(f"Loaded bronze.{t}")

    spark.stop()


if __name__ == "__main__":
    main()