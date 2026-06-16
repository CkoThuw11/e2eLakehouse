from __future__ import annotations

from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator
import os
import subprocess
import sys


def log_failure(context):
    ti = context.get("task_instance")
    dag = context.get("dag")
    dag_id = dag.dag_id if dag else "unknown_dag"
    task_id = ti.task_id if ti else "unknown_task"
    logical_date = context.get("logical_date")
    print(f"[FAILED] DAG={dag_id}, TASK={task_id}, LOGICAL_DATE={logical_date}.")


def run_spark_script(script_path: str) -> None:
    """
    Run a PySpark script in a subprocess to avoid SparkContext conflicts
    between tasks and to get clean JVM isolation per job.
    """
    spark_home = "/home/airflow/.local/lib/python3.11/site-packages/pyspark"

    env = os.environ.copy()
    env.update({
        "SPARK_CONF_DIR": "/opt/spark-conf",
        "JAVA_HOME": "/usr/lib/jvm/java-17-openjdk-amd64",
        "SPARK_HOME": spark_home,
        "PYSPARK_PYTHON": sys.executable,
        "PYSPARK_DRIVER_PYTHON": sys.executable,
        # Pass through S3/MinIO credentials (already in env from docker-compose)
        "AWS_ACCESS_KEY_ID": env.get("AWS_ACCESS_KEY_ID", ""),
        "AWS_SECRET_ACCESS_KEY": env.get("AWS_SECRET_ACCESS_KEY", ""),
        "AWS_REGION": env.get("AWS_REGION", "us-east-1"),
    })

    print(f"Running spark script: {script_path}")
    print(f"Using Python: {sys.executable}")
    print(f"SPARK_HOME: {spark_home}")

    result = subprocess.run(
        [sys.executable, script_path],
        env=env,
        capture_output=False,   # stream stdout/stderr directly to task logs
        check=False,
    )

    if result.returncode != 0:
        raise RuntimeError(
            f"Spark script {script_path} failed with exit code {result.returncode}"
        )


default_args = {
    "owner": "dw-team",
    "depends_on_past": False,
    "retries": 2,
    "retry_delay": timedelta(minutes=5),
    "email_on_failure": False,
    "on_failure_callback": log_failure,
}

with DAG(
    dag_id="bronze_ingest_dag",
    description="Create Iceberg schemas and ingest the Bronze layer from PostgreSQL.",
    default_args=default_args,
    start_date=datetime(2026, 5, 27),
    schedule_interval=None,  # Triggered by lakehouse_pipeline_dag (or manually)
    catchup=False,
    is_paused_upon_creation=False,
    tags=["spark", "bronze", "iceberg", "lakehouse"],
) as dag:

    create_iceberg_schemas = PythonOperator(
        task_id="create_iceberg_schemas",
        python_callable=run_spark_script,
        op_kwargs={"script_path": "/opt/spark-app/create_schema.py"},
        execution_timeout=timedelta(minutes=15),
    )

    ingest_bronze = PythonOperator(
        task_id="ingest_bronze",
        python_callable=run_spark_script,
        op_kwargs={"script_path": "/opt/spark-app/ingest_bronze.py"},
        execution_timeout=timedelta(minutes=60),
    )

    create_iceberg_schemas >> ingest_bronze