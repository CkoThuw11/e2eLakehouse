# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

End-to-end Northwind data lakehouse: Apache Iceberg on MinIO, with Spark for bronze ingest, dbt for silver/gold transforms, Trino as the query engine, Airflow for orchestration, a Streamlit dashboard, and a Groq-powered text-to-SQL CLI agent. All services run via `docker-compose.yaml` at the repo root.

## Architecture (big picture)

Data flows through three Iceberg schemas in a single catalog `iceberg`, each layer owned by a different tool:

- **Bronze** (`iceberg.bronze`) — raw Northwind tables loaded from PostgreSQL by `docker/spark/spark-app/ingest_bronze.py` running in the `spark-ingest` container.
- **Silver** (`iceberg.silver`) — cleaned/typed staging models in `dbt/models/staging/` (7 `stg_*` models).
- **Gold** (`iceberg.gold`) — star schema in `dbt/models/gold/`: 5 dims (`dim_customers`, `dim_products`, `dim_employees`, `dim_date`) + `fact_sales` + `wide_sales_forecast` (1 row per day × category with 7d/30d rolling sums, used for the dashboard forecast tab and ML retraining).

The Hive Metastore (`docker/hive`) holds Iceberg table metadata; MinIO (`warehouse/` bucket) holds the underlying data files. Trino, Spark, and dbt all point at the same Hive Metastore + MinIO via configs in `docker/trino/`, `docker/spark/spark-config/`, and `dbt/profiles.yml`. Changing storage endpoints requires touching all three.

Downstream consumers of `iceberg.gold` via Trino:
- **Streamlit** (`docker/streamlit/app.py`) — 3-tab analytics dashboard, all queries cached 1 hour, sidebar date range drives all tabs.
- **Groq agent** (`docker/agent/`) — text-to-SQL CLI. Flow: `question → Groq LLaMA 3.3 70B → sql_guard (SELECT-only enforcement) → Trino → Groq formats answer`. Retries once on SQL failure with the error fed back to the model. Requires `GROQ_API_KEY` in `.env`.

Airflow DAGs live in `docker/airflow/dags/`:
- `service_healthcheck_dag` — every 10 min, parallel checks of PostgreSQL, MinIO, Trino, Spark.
- `bronze_ingest_dag` — wraps the spark-submit bronze ingest.
- `dbt_transform_dag` — runs silver then gold dbt models.
- `model_retrain_dag` — retrains the forecasting model from `wide_sales_forecast`.

## Common commands

### Bring the stack up

```bash
cp .env.example .env            # add GROQ_API_KEY if using the agent
docker compose up -d --build
docker compose ps               # airflow-init and create-minio-bucket exit 0; this is expected
```

WSL/Windows gotcha: shell scripts under `docker/` must have **LF** line endings or Spark builds fail with `not found`.

### Initial data load (run once after stack is up)

```bash
docker exec -it spark-ingest spark-submit /opt/spark-app/create_schema.py
docker exec -it spark-ingest spark-submit /opt/spark-app/ingest_bronze.py
```

### dbt

```bash
docker exec -it dbt dbt deps
docker exec -it dbt dbt run  --select staging
docker exec -it dbt dbt test --select staging
docker exec -it dbt dbt run  --select gold
docker exec -it dbt dbt test --select gold

# Single model / test
docker exec -it dbt dbt run  --select stg_orders
docker exec -it dbt dbt test --select fact_sales
```

### Trino

```bash
docker exec -it trino trino
# Then: SHOW SCHEMAS FROM iceberg;  SHOW TABLES FROM iceberg.gold;
```

### Groq agent

```bash
docker compose run --rm groq-agent                                          # 5 sample questions
docker compose run --rm groq-agent python main.py -q "Top 5 products?"      # one-shot
docker compose run --rm groq-agent python main.py --interactive             # REPL
docker compose run --rm groq-agent pytest                                   # tests in docker/agent/tests/
```

### Airflow

```bash
docker exec -it airflow-scheduler airflow dags unpause service_healthcheck_dag
docker exec -it airflow-scheduler airflow dags trigger  service_healthcheck_dag
```

### Service URLs

| Service | URL | Credentials |
|---|---|---|
| Airflow | http://localhost:8081 | airflow / airflow |
| MinIO Console | http://localhost:9001 | admin / admin123 |
| Trino UI | http://localhost:8090 | any username, no password |
| Streamlit | http://localhost:8501 | — |

## Conventions worth knowing

- The `iceberg` catalog name is hardcoded across Trino/Spark/dbt configs — renaming it is a cross-cutting change.
- dbt `profiles.yml` is committed and targets the in-cluster Trino (`trino:8080`), not localhost. Run dbt inside the `dbt` container, not from the host.
- Bronze ingest is idempotent (truncate-and-reload pattern); silver/gold are `table` materializations, so dbt runs are also idempotent.
- The Groq agent enforces SELECT-only via `sql_guard` before sending to Trino — do not bypass this check when extending the agent.
- See `README_Trino.md` for additional Trino setup notes beyond the main README.
