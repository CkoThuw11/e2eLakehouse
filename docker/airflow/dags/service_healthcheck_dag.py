from __future__ import annotations

import socket
import urllib.request
from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.python import PythonOperator


DEFAULT_TIMEOUT_SECONDS = 5


def check_tcp_connection(host: str, port: int, service_name: str) -> None:
    """
    Check whether a TCP service is reachable.
    This is suitable for database/service ports such as PostgreSQL.
    """
    try:
        with socket.create_connection((host, port), timeout=DEFAULT_TIMEOUT_SECONDS):
            print(f"[OK] {service_name} is reachable at {host}:{port}")
    except Exception as exc:
        raise RuntimeError(
            f"[FAILED] {service_name} is not reachable at {host}:{port}. Error: {exc}"
        ) from exc


def check_http_endpoint(url: str, service_name: str) -> None:
    """
    Check whether an HTTP endpoint returns a successful status code.
    This is suitable for MinIO, Trino, Spark UI, etc.
    """
    try:
        request = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(request, timeout=DEFAULT_TIMEOUT_SECONDS) as response:
            status_code = response.getcode()

        if 200 <= status_code < 400:
            print(f"[OK] {service_name} responded with HTTP {status_code}: {url}")
        else:
            raise RuntimeError(
                f"{service_name} returned unexpected HTTP status {status_code}: {url}"
            )

    except Exception as exc:
        raise RuntimeError(
            f"[FAILED] {service_name} healthcheck failed at {url}. Error: {exc}"
        ) from exc


def check_postgres() -> None:
    check_tcp_connection(
        host="northwind-db",
        port=5432,
        service_name="PostgreSQL Northwind"
    )


def check_minio() -> None:
    check_http_endpoint(
        url="http://minio:9000/minio/health/live",
        service_name="MinIO"
    )


def check_trino() -> None:
    check_http_endpoint(
        url="http://trino:8080/v1/info",
        service_name="Trino"
    )


def check_spark() -> None:
    """
    Spark UI can be exposed on different ports depending on your setup.
    In this project overview, Spark exposes 4040 and 8080.
    We first try Spark Master/UI on 8080, then fallback to 4040.
    """
    try:
        check_http_endpoint(
            url="http://spark:8080",
            service_name="Spark UI / Master"
        )
    except Exception:
        check_http_endpoint(
            url="http://spark:4040",
            service_name="Spark Application UI"
        )


default_args = {
    "owner": "dw-team",
    "depends_on_past": False,
    "retries": 1,
    "retry_delay": timedelta(minutes=1),
}


with DAG(
    dag_id="service_healthcheck_dag",
    description="Monitor health status of Postgres, MinIO, Trino, and Spark services.",
    default_args=default_args,
    start_date=datetime(2026, 5, 27),
    schedule_interval="*/10 * * * *",
    catchup=False,
    tags=["monitoring", "lakehouse", "healthcheck"],
) as dag:

    check_postgres_task = PythonOperator(
        task_id="check_postgres",
        python_callable=check_postgres,
    )

    check_minio_task = PythonOperator(
        task_id="check_minio",
        python_callable=check_minio,
    )

    check_trino_task = PythonOperator(
        task_id="check_trino",
        python_callable=check_trino,
    )

    check_spark_task = PythonOperator(
        task_id="check_spark",
        python_callable=check_spark,
    )

    [
        check_postgres_task,
        check_minio_task,
        check_trino_task,
        check_spark_task,
    ]