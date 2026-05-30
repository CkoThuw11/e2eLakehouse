# The modern lakehouse architecture

## Repository Structure
```
├── REAMDE.md
├── docker
│   ├── hive
│   │   └── hive-site.xml
│   ├── postgres
│   │   └── init.sql
│   └── spark
│       ├── Dockerfile
│       ├── download_jars.sh
│       ├── spark-app
│       │   ├── create_schema.py
│       │   └── ingest_bronze.py
│       └── spark-config
│           ├── core-site.xml
│           ├── hive-site.xml
│           └── spark-defaults.conf
├── dbt/
│   └── models/
└── docker-compose.yaml
```
## Getting Started
### Step 1 — Configure Environment

```bash
cp .env.example .env
```
### Step 2 — Start the Pipeline

```bash
docker compose up -d --build
```
### Step 3 — Verify Services

```bash
docker compose ps
``` 
### Step 4 — Create Schema
```bash
docker exec -it spark-ingest spark-submit /opt/spark-app/create_schema.py
```
### Step 5 - Ingest data into Bronze layer
```bash
docker exec -it spark-ingest spark-submit /opt/spark-app/ingest_bronze.py
```
### Step 6 - Transform data into Silver layer (dbt) 
- After the data is successfully ingested into the Bronze layer, use dbt to clean, filter, and transform the data into the Silver layer.
- If you are running dbt via Docker Compose, execute the following command:
```bash 
docker  exec -it dbt dbt run
```
- Note: If you are running dbt locally outside of Docker, navigate to the dbt/ directory and execute dbt run --select silver.
#### dbt Project Structure & Logic
Staging Models (dbt/models/staging/stg_*.sql):
-   Purpose: Read directly from the Bronze layer.
-   Responsibility: Perform light cleaning, column renaming (e.g., customerID to customer_id), and data type casting. Each staging model maps 1-to-1 with a source table.
Silver Models (dbt/models/silver/*.sql):
-   Purpose: Create integrated datasets representing the "single source of truth".
-   Responsibility: Built on top of staging models to apply business rules and join entities.
(Optional) If you want to run specific models (e.g., only silver), you can use the --select flag:
 ```bash 
docker exec -it dbt dbt run --select silver
```

## MinIO Warehouse Layout

Expected warehouse structure:

```text
warehouse/
├── bronze/
│   ├── customers/
│   ├── orders/
│   ├── products/
│   └── ...
├── silver/
└── gold/
```

Each Iceberg table contains:

```text
metadata/
data/
```
## Planned next steps:
-   Build Gold layer
-   Add CDC ingestion
-   Implement `MERGE INTO`
-   Add partition optimization
-   Add orchestration (Airflow / Dagster)
-   Add Trino query engine
-   Add incremental ingestion pipeline
