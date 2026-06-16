# Northwind Lakehouse

End-to-end data lakehouse built on Apache Iceberg + Spark + Trino, with dbt transformations, an Airflow healthcheck, a Streamlit dashboard, and a Groq-powered text-to-SQL agent.

---

## Architecture

```
PostgreSQL (Northwind)
        │
        ▼  spark-submit
  Bronze (Iceberg)
        │
        ▼  dbt staging
  Silver (Iceberg)
        │
        ▼  dbt gold
  Gold (Iceberg)  ──► Trino ──► Streamlit Dashboard
                            └──► Groq AI Agent (text-to-SQL)
```

| Layer | Iceberg Schema | Tool | Purpose |
|---|---|---|---|
| Bronze | `iceberg.bronze` | Spark | Raw Northwind tables |
| Silver | `iceberg.silver` | dbt `models/staging/` | Cleaned, typed staging models |
| Gold | `iceberg.gold` | dbt `models/gold/` | Star schema — dims, fact, wide ML table |

---

## Repository Layout

```
e2eLakehouse/
├── .env.example
├── docker-compose.yaml
├── dbt/models/
│   ├── staging/          → 7 silver models
│   └── gold/             → 5 dims + 1 fact + 1 wide table
└── docker/
    ├── agent/            → Groq text-to-SQL CLI
    ├── airflow/dags/
    ├── dbt-spark/
    ├── hive/
    ├── ml/
    ├── postgres/
    ├── spark/
    ├── streamlit/        → Live analytics dashboard
    └── trino/
```

---

## Quick Start

### 1. Configure environment

```bash
cp .env.example .env
# Add your Groq key if you want the AI agent:
# GROQ_API_KEY=<key from https://console.groq.com>
```

### 2. Start all services

```bash
docker compose up -d --build
```

> **Windows / WSL:** If Spark build fails with `not found` errors, ensure `*.sh` files have **LF** line endings (not CRLF).

### 3. Verify services

```bash
docker compose ps
```

`airflow-init` and `create-minio-bucket` exit after completing — this is expected.

### 4. Create Iceberg schemas

```bash
docker exec -it spark-ingest spark-submit /opt/spark-app/create_schema.py
```

### 5. Ingest Bronze layer

```bash
docker exec -it spark-ingest spark-submit /opt/spark-app/ingest_bronze.py
```

### 6. Run dbt transformations

```bash
docker exec -it dbt dbt deps

# Silver
docker exec -it dbt dbt run  --select staging
docker exec -it dbt dbt test --select staging

# Gold
docker exec -it dbt dbt run  --select gold
docker exec -it dbt dbt test --select gold
```

---

## Service URLs

| Service | URL | Credentials |
|---|---|---|
| Airflow | http://localhost:8081 | `airflow` / `airflow` |
| MinIO Console | http://localhost:9001 | `admin` / `admin123` |
| Trino UI | http://localhost:8090 | any username, no password |
| Streamlit Dashboard | http://localhost:8501 | — |

---

## Streamlit Dashboard

Live analytics dashboard connected to `iceberg.gold` via Trino. Starts automatically with `docker compose up`.

| Tab | Content |
|---|---|
| Revenue Overview | Metric cards · Daily revenue chart · Revenue by category |
| Products & Customers | Top 10 products · Category pie · Top 10 customers |
| Revenue Forecast | Historical revenue · 7d/30d rolling averages · 30-day linear projection ±15% |

All queries are cached with a 1-hour TTL. A sidebar date range filter drives all tabs.

---

## Groq AI Agent (Text-to-SQL)

CLI agent that converts natural language to SQL via the Groq API (LLaMA 3.3 70B), executes on Trino, and returns a plain-language answer.

**Flow:** `question → Groq (generate SQL) → sql_guard (SELECT-only) → Trino → Groq (format answer) → print`

If SQL fails, the agent retries once with the error fed back to the model.

```bash
# Run 5 sample questions
docker compose run --rm groq-agent

# Single question
docker compose run --rm groq-agent python main.py -q "Top 5 products last month?"

# Interactive mode
docker compose run --rm groq-agent python main.py --interactive
```

---

## Trino

Single-node coordinator with an Iceberg catalog backed by Hive Metastore and MinIO.

```bash
# Connect to Trino CLI
docker exec -it trino trino

# Explore
SHOW SCHEMAS FROM iceberg;
SHOW TABLES FROM iceberg.gold;

# Sample queries
SELECT * FROM iceberg.bronze.order_details LIMIT 10;
SELECT * FROM iceberg.gold.fact_sales       LIMIT 10;
SELECT sale_date, product_category, total_revenue
FROM iceberg.gold.wide_sales_forecast
ORDER BY sale_date DESC LIMIT 20;
```

---

## dbt Models

```
models/staging/          models/gold/
├── stg_customers        ├── dim_customers
├── stg_orders           ├── dim_products
├── stg_order_details    ├── dim_employees
├── stg_products         ├── dim_date
├── stg_categories       ├── fact_sales
├── stg_employees        └── wide_sales_forecast
└── stg_suppliers
```

| Table | Grain |
|---|---|
| `dim_customers` | 1 row per customer |
| `dim_products` | 1 row per product (includes category & supplier) |
| `dim_employees` | 1 row per employee |
| `dim_date` | 1 calendar day (1996-01-01 → 1999-01-01) |
| `fact_sales` | 1 row per order line item |
| `wide_sales_forecast` | 1 row per day × category with 7d/30d rolling sums |

---

## Airflow Healthcheck DAG

- **DAG ID:** `service_healthcheck_dag`
- **Schedule:** every 10 minutes
- **Monitors:** PostgreSQL · MinIO · Trino · Spark (all tasks run in parallel)

```bash
# Enable the DAG
docker exec -it airflow-scheduler airflow dags unpause service_healthcheck_dag

# Trigger manually
docker exec -it airflow-scheduler airflow dags trigger service_healthcheck_dag
```

![Airflow Healthcheck DAG](docs/images/airflow-healthcheck-dag.png)

---

## MinIO Warehouse Layout

```
warehouse/
├── bronze/   (categories, customers, employees, orders, order_details, products, suppliers)
├── silver/   (stg_customers, stg_orders, stg_order_details, stg_products, stg_categories, stg_employees, stg_suppliers)
└── gold/     (dim_customers, dim_products, dim_employees, dim_date, fact_sales, wide_sales_forecast)
```
