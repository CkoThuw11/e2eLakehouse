from pyspark.sql import SparkSession

def main():

    spark = (
        SparkSession.builder
        .appName("Create Iceberg Tables (Hive Catalog)")
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

    spark.sql("CREATE DATABASE IF NOT EXISTS bronze")
    spark.sql("CREATE DATABASE IF NOT EXISTS silver")
    spark.sql("CREATE DATABASE IF NOT EXISTS gold")

    spark.sql("""
        CREATE TABLE IF NOT EXISTS bronze.categories (
            category_id SMALLINT,
            category_name STRING,
            description STRING,
            picture BINARY
        )
        USING iceberg
    """)

    spark.sql("""
        CREATE TABLE IF NOT EXISTS bronze.customers (
            customer_id STRING,
            company_name STRING,
            contact_name STRING,
            contact_title STRING,
            address STRING,
            city STRING,
            region STRING,
            postal_code STRING,
            country STRING,
            phone STRING,
            fax STRING
        )
        USING iceberg
    """)

    spark.sql("""
        CREATE TABLE IF NOT EXISTS bronze.employees (
            employee_id SMALLINT,
            last_name STRING,
            first_name STRING,
            title STRING,
            title_of_courtesy STRING,
            birth_date DATE,
            hire_date DATE,
            address STRING,
            city STRING,
            region STRING,
            postal_code STRING,
            country STRING,
            home_phone STRING,
            extension STRING,
            photo BINARY,
            notes STRING,
            reports_to SMALLINT,
            photo_path STRING
        )
        USING iceberg
    """)

    spark.sql("""
        CREATE TABLE IF NOT EXISTS bronze.orders (
            order_id SMALLINT,
            customer_id STRING,
            employee_id SMALLINT,
            order_date DATE,
            required_date DATE,
            shipped_date DATE,
            ship_via SMALLINT,
            freight DOUBLE,
            ship_name STRING,
            ship_address STRING,
            ship_city STRING,
            ship_region STRING,
            ship_postal_code STRING,
            ship_country STRING
        )
        USING iceberg
    """)

    spark.sql("""
        CREATE TABLE IF NOT EXISTS bronze.products (
            product_id SMALLINT,
            product_name STRING,
            supplier_id SMALLINT,
            category_id SMALLINT,
            quantity_per_unit STRING,
            unit_price DOUBLE,
            units_in_stock SMALLINT,
            units_on_order SMALLINT,
            reorder_level SMALLINT,
            discontinued INT
        )
        USING iceberg
    """)

    spark.sql("""
        CREATE TABLE IF NOT EXISTS bronze.order_details (
            order_id SMALLINT,
            product_id SMALLINT,
            unit_price DOUBLE,
            quantity SMALLINT,
            discount DOUBLE
        )
        USING iceberg
    """)

    spark.sql("""
        CREATE TABLE IF NOT EXISTS bronze.suppliers (
            supplier_id SMALLINT,
            company_name STRING,
            contact_name STRING,
            contact_title STRING,
            address STRING,
            city STRING,
            region STRING,
            postal_code STRING,
            country STRING,
            phone STRING,
            fax STRING,
            homepage STRING
        )
        USING iceberg
    """)

    print("Full Northwind Iceberg Bronze schema created")

    spark.stop()


if __name__ == "__main__":
    main()