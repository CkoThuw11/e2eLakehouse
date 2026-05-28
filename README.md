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
└── docker-compose.yaml
```

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


# Future Improvements

Planned next steps:

- Build Silver layer
- Build Gold layer
- Add CDC ingestion
- Implement `MERGE INTO`
- Add partition optimization
- Add orchestration (Airflow / Dagster)
- Add Trino query engine
- Add dbt transformations
- Add incremental ingestion pipeline

