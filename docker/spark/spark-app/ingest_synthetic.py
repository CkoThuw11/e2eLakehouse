"""Synthetic Northwind data generator.

Reads the existing bronze.orders / order_details / customers / employees /
products tables to learn realistic distributions, then generates synthetic
orders for dates AFTER the current max(order_date) and APPENDS them to the
bronze Iceberg tables (no overwrite, so downstream dbt incremental models
will pick up only the new rows).

Configuration via env vars:
    SYNTHETIC_DAYS        — number of new days to add        (default 30)
    SYNTHETIC_ORDERS_DAY  — average orders per day            (default 12)
    SYNTHETIC_MAX_LINES   — max line items per order          (default 4)
    SYNTHETIC_SEED        — RNG seed for reproducibility      (default 42)
"""
from __future__ import annotations

import os
import random
from datetime import timedelta

from pyspark.sql import Row, SparkSession
from pyspark.sql.functions import col, max as smax


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default


def build_spark() -> SparkSession:
    return (
        SparkSession.builder
        .appName("Synthetic Northwind Ingest")
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


def main() -> None:
    days        = _env_int("SYNTHETIC_DAYS", 30)
    per_day_avg = _env_int("SYNTHETIC_ORDERS_DAY", 12)
    max_lines   = _env_int("SYNTHETIC_MAX_LINES", 4)
    seed        = _env_int("SYNTHETIC_SEED", 42)
    rng = random.Random(seed)

    spark = build_spark()

    orders        = spark.table("bronze.orders")
    order_details = spark.table("bronze.order_details")
    customers     = [r["customer_id"] for r in spark.table("bronze.customers").select("customer_id").collect()]
    employees     = [r["employee_id"] for r in spark.table("bronze.employees").select("employee_id").collect()]
    products_rows = spark.table("bronze.products").select("product_id", "unit_price").collect()
    products      = [(r["product_id"], float(r["unit_price"] or 0.0)) for r in products_rows]

    if not customers or not employees or not products:
        raise RuntimeError("Bronze reference tables are empty — run ingest_bronze first.")

    bounds = orders.agg(smax("order_id").alias("mx_id"), smax("order_date").alias("mx_dt")).collect()[0]
    next_id   = (bounds["mx_id"] or 0) + 1
    start_day = (bounds["mx_dt"] + timedelta(days=1)) if bounds["mx_dt"] else None
    if start_day is None:
        raise RuntimeError("Could not determine max order_date in bronze.orders.")

    print(f"[INFO] Generating {days} day(s) of synthetic data starting {start_day} "
          f"(avg {per_day_avg} orders/day, next order_id={next_id})")

    new_orders: list[Row] = []
    new_details: list[Row] = []
    ship_vias = [1, 2, 3]
    discounts = [0.0, 0.0, 0.0, 0.05, 0.10, 0.15, 0.20, 0.25]

    for d in range(days):
        order_date = start_day + timedelta(days=d)
        # Normal-ish daily count around the average
        n_orders = max(1, int(rng.gauss(per_day_avg, per_day_avg * 0.25)))
        for _ in range(n_orders):
            oid = next_id
            next_id += 1
            cust = rng.choice(customers)
            emp  = rng.choice(employees)
            required = order_date + timedelta(days=rng.randint(7, 21))
            shipped  = order_date + timedelta(days=rng.randint(1, 7))
            freight  = round(rng.uniform(5.0, 120.0), 2)

            new_orders.append(Row(
                order_id        = oid,
                customer_id     = cust,
                employee_id     = emp,
                order_date      = order_date,
                required_date   = required,
                shipped_date    = shipped,
                ship_via        = rng.choice(ship_vias),
                freight         = freight,
                ship_name       = f"Synthetic Ship {oid}",
                ship_address    = f"{rng.randint(1, 999)} Synthetic St",
                ship_city       = "Synthetic City",
                ship_region     = None,
                ship_postal_code= str(rng.randint(10000, 99999)),
                ship_country    = "Synthland",
            ))

            n_lines = rng.randint(1, max_lines)
            chosen  = rng.sample(products, k=min(n_lines, len(products)))
            for product_id, base_price in chosen:
                price = round(base_price * rng.uniform(0.9, 1.1), 2) if base_price > 0 else round(rng.uniform(5, 60), 2)
                qty   = rng.randint(1, 30)
                new_details.append(Row(
                    order_id    = oid,
                    product_id  = product_id,
                    unit_price  = price,
                    quantity    = qty,
                    discount    = rng.choice(discounts),
                ))

    print(f"[INFO] Built {len(new_orders)} orders / {len(new_details)} order_details — appending to bronze")

    # Build DataFrames aligned to existing bronze schemas, then append.
    orders_df  = spark.createDataFrame(new_orders, schema=orders.schema)
    details_df = spark.createDataFrame(new_details, schema=order_details.schema)

    orders_df.writeTo("bronze.orders").append()
    print("[INFO] Appended to bronze.orders")

    details_df.writeTo("bronze.order_details").append()
    print("[INFO] Appended to bronze.order_details")

    spark.stop()
    print("[INFO] Done")


if __name__ == "__main__":
    main()
