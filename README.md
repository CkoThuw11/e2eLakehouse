# The Modern Lakehouse Architecture

## Repository Structure

```
e2eLakehouse/
├── README.md
├── .env.example
├── docker-compose.yaml
├── docs/
│   └── images/
│       └── airflow-healthcheck-dag.png
└── docker/
    ├── airflow/
    │   ├── dags/
    │   │   └── service_healthcheck_dag.py
    │   └── logs/                            # Auto-generated, gitignored
    ├── hive/
    │   └── hive-site.xml
    ├── postgres/
    │   └── init.sql
    ├── spark/
    │   ├── Dockerfile
    │   ├── download_jars.sh
    │   ├── spark-app/
    │   │   ├── create_schema.py
    │   │   └── ingest_bronze.py
    │   └── spark-config/
    │       ├── core-site.xml
    │       ├── hive-site.xml
    │       └── spark-defaults.conf
    └── trino/
        └── catalog/
            └── iceberg.properties
```

---

## Quick Start

### Step 1 — Configure Environment

```bash
cp .env.example .env
```

### Step 2 — Start All Services

```bash
docker compose up -d --build
```

> **Note:** On Windows, if you encounter `not found` errors during the Spark build,
> ensure that shell scripts (`*.sh`) have **LF** line endings (not CRLF).

### Step 3 — Verify Services

```bash
docker compose ps
```

All services should show `running` status. The `airflow-init` and `create-minio-bucket`
containers will exit after completing their initialization tasks — this is expected.

### Step 4 — Create Iceberg Schema

```bash
docker exec -it spark-lakehouse spark-submit /opt/spark-app/create_schema.py
```

### Step 5 — Ingest Data into Bronze Layer

```bash
docker exec -it spark-lakehouse spark-submit /opt/spark-app/ingest_bronze.py
```

---

## Web UI Access

| Service | URL | Credentials |
|---|---|---|
| **Airflow** | [http://localhost:8081](http://localhost:8081) | `airflow` / `airflow` |
| **MinIO Console** | [http://localhost:9001](http://localhost:9001) | `admin` / `admin123` |
| **Trino** | [http://localhost:8090](http://localhost:8090) | any username, no password |
| **Spark UI** | [http://localhost:4040](http://localhost:4040) | — |

---

## Airflow — Service Healthcheck DAG

This project includes an **Apache Airflow** setup with a DAG that monitors the health
of all lakehouse services.

### Overview

- **DAG ID:** `service_healthcheck_dag`
- **Schedule:** Every 10 minutes (`*/10 * * * *`)
- **Owner:** `dw-team`
- **Tags:** `monitoring`, `lakehouse`, `healthcheck`

### What It Monitors

| Task ID | Service | Method | Target |
|---|---|---|---|
| `check_postgres` | PostgreSQL (Northwind) | TCP socket | `northwind-db:5432` |
| `check_minio` | MinIO | HTTP GET | `http://minio:9000/minio/health/live` |
| `check_trino` | Trino | HTTP GET | `http://trino:8080/v1/info` |
| `check_spark` | Spark | HTTP GET | `http://spark:8080` (fallback: `:4040`) |

All 4 tasks run **in parallel** (no dependency between them).

### Airflow Architecture (Docker)

The Airflow stack consists of 3 containers + 1 init container:

| Container | Role |
|---|---|
| `airflow-db` | PostgreSQL 15 — Airflow metadata database (port `5434`) |
| `airflow-init` | Runs `airflow db migrate` + creates admin user, then exits |
| `airflow-webserver` | Airflow Web UI on port `8081` |
| `airflow-scheduler` | Executes DAGs on schedule |

### Usage After Cloning

1. **Clone the repository and start services:**

   ```bash
   git clone https://github.com/CkoThuw11/e2eLakehouse.git
   cd e2eLakehouse
   cp .env.example .env
   docker compose up -d --build
   ```

2. **Wait for initialization** (~30-60 seconds for `airflow-init` to complete):

   ```bash
   # Check if airflow-init has finished
   docker compose logs airflow-init --tail 5
   ```

3. **Access Airflow UI:**
   - Open [http://localhost:8081](http://localhost:8081)
   - Login: **username** = `airflow`, **password** = `airflow`

4. **Enable the DAG:**
   - The DAG is **paused by default**. Toggle the switch next to `service_healthcheck_dag` to enable it.
   - Or enable via CLI:
     ```bash
     docker exec -it airflow-scheduler airflow dags unpause service_healthcheck_dag
     ```

5. **Trigger a manual run** (optional):

   ```bash
   docker exec -it airflow-scheduler airflow dags trigger service_healthcheck_dag
   ```

6. **Verify the DAG is registered:**

   ```bash
   docker exec -it airflow-scheduler airflow dags list
   ```

7. **Check for import errors:**

   ```bash
   docker exec -it airflow-scheduler airflow dags list-import-errors
   ```

### Proof of Successful Execution

The DAG has been tested and runs successfully:

![Airflow Healthcheck DAG running successfully](docs/images/airflow-healthcheck-dag.png)

### Adding New Healthcheck Tasks

To monitor additional services, edit `docker/airflow/dags/service_healthcheck_dag.py`:

1. Create a new function using `check_tcp_connection()` (for database ports) or `check_http_endpoint()` (for HTTP services).
2. Add a new `PythonOperator` task in the DAG definition.
3. The DAG will auto-reload — no restart needed.

---

## Trino Query Engine

Trino is configured as a query engine with an **Iceberg catalog** connected to the Hive Metastore and MinIO.

### Usage

```bash
# Connect to Trino CLI
docker exec -it trino trino

# Example queries
SHOW CATALOGS;
SHOW SCHEMAS FROM iceberg;
SELECT * FROM iceberg.bronze.customers LIMIT 10;
```

---

## MinIO Warehouse Layout

Expected warehouse structure:

```text
warehouse/
├── bronze/
│   ├── categories/
│   ├── customers/
│   ├── employees/
│   ├── orders/
│   ├── order_details/
│   ├── products/
│   └── suppliers/
├── silver/
└── gold/
```

Each Iceberg table contains:

```text
<table_name>/
├── metadata/
└── data/
```

---

## Future Improvements

Planned next steps:

- Build Silver layer
- Build Gold layer
- Add CDC ingestion
- Implement `MERGE INTO`
- Add partition optimization
- ~~Add orchestration (Airflow / Dagster)~~ ✅ Airflow added
- ~~Add Trino query engine~~ ✅ Trino added
- Add dbt transformations
- Add incremental ingestion pipeline
