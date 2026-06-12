from __future__ import annotations

import json
import os
import subprocess
from datetime import datetime, timedelta

import boto3
from airflow import DAG
from airflow.hooks.base import BaseHook
from airflow.operators.python import PythonOperator
from airflow.sensors.external_task import ExternalTaskSensor


def log_failure(context):
    ti = context.get("task_instance")
    dag = context.get("dag")

    dag_id = dag.dag_id if dag else "unknown_dag"
    task_id = ti.task_id if ti else "unknown_task"
    logical_date = context.get("logical_date")

    print(
        f"[FAILED] DAG={dag_id}, TASK={task_id}, LOGICAL_DATE={logical_date}. "
        "Check logs for details."
    )


def get_minio_config() -> dict:
    conn = BaseHook.get_connection("minio_default")
    extra = conn.extra_dejson or {}

    endpoint_url = extra.get("endpoint_url") or f"http://{conn.host}:{conn.port}"
    bucket = extra.get("bucket", "warehouse")

    return {
        "endpoint_url": endpoint_url,
        "access_key": conn.login,
        "secret_key": conn.password,
        "bucket": bucket,
    }


def get_trino_config() -> dict:
    conn = BaseHook.get_connection("trino_default")

    return {
        "host": conn.host,
        "port": str(conn.port or 8080),
        "user": conn.login or "airflow",
    }


def run_prophet_training() -> None:
    minio = get_minio_config()
    trino = get_trino_config()

    env = os.environ.copy()
    env.update(
        {
            "MINIO_ENDPOINT_URL": minio["endpoint_url"],
            "MINIO_ACCESS_KEY": minio["access_key"],
            "MINIO_SECRET_KEY": minio["secret_key"],
            "MINIO_BUCKET": minio["bucket"],
            "TRINO_HOST": trino["host"],
            "TRINO_PORT": trino["port"],
            "TRINO_USER": trino["user"],
        }
    )

    result = subprocess.run(
        ["python", "/opt/ml/train_prophet.py"],
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    print("[TRAINING STDOUT]")
    print(result.stdout)

    print("[TRAINING STDERR]")
    print(result.stderr)

    if result.returncode != 0:
        raise RuntimeError(f"Prophet training failed with exit code {result.returncode}")


def log_metrics() -> None:
    minio = get_minio_config()

    s3 = boto3.client(
        "s3",
        endpoint_url=minio["endpoint_url"],
        aws_access_key_id=minio["access_key"],
        aws_secret_access_key=minio["secret_key"],
    )

    obj = s3.get_object(
        Bucket=minio["bucket"],
        Key="models/prophet_v1_metrics.json",
    )

    metrics = json.loads(obj["Body"].read().decode("utf-8"))

    print("[MODEL METRICS]")
    print(json.dumps(metrics, indent=2))


default_args = {
    "owner": "dw-team",
    "depends_on_past": False,
    "email_on_failure": False,
    "on_failure_callback": log_failure,
}


with DAG(
    dag_id="model_retrain_dag",
    description="Weekly Prophet retraining from Gold wide_sales_forecast.",
    default_args=default_args,
    start_date=datetime(2026, 5, 27),
    schedule_interval="0 2 * * 1",
    catchup=False,
    tags=["ml", "prophet", "training", "gold"],
) as dag:

    wait_for_dbt_transform = ExternalTaskSensor(
        task_id="wait_for_dbt_transform",
        external_dag_id="dbt_transform_dag",
        external_task_id=None,
        execution_delta=timedelta(hours=1),
        timeout=3600,
        poke_interval=60,
        mode="reschedule",
    )

    run_prophet_training_task = PythonOperator(
        task_id="run_prophet_training",
        python_callable=run_prophet_training,
        retries=2,
        retry_delay=timedelta(minutes=5),
    )

    log_metrics_task = PythonOperator(
        task_id="log_metrics",
        python_callable=log_metrics,
    )

    wait_for_dbt_transform >> run_prophet_training_task >> log_metrics_task