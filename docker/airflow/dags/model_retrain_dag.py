from __future__ import annotations

import json
import os
import subprocess
from datetime import datetime, timedelta

import boto3
from airflow import DAG
from airflow.hooks.base import BaseHook
from airflow.operators.python import PythonOperator


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
    return {
        "endpoint_url": os.getenv("MINIO_ENDPOINT", "http://minio:9000"),
        "access_key": os.getenv("MINIO_ACCESS_KEY", "admin"),
        "secret_key": os.getenv("MINIO_SECRET_KEY", "admin123"),
        "bucket": os.getenv("MINIO_BUCKET", "warehouse"),
    }


def get_trino_config() -> dict:
    return {
        "host": os.getenv("TRINO_HOST", "trino"),
        "port": os.getenv("TRINO_PORT", "8080"),
        "user": os.getenv("TRINO_USER", "airflow"),
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


def _latest_metrics_key(s3, bucket: str) -> str:
    """Resolve the metrics JSON key for the most recent training run by
    reading the models/latest_overall.txt pointer that train_prophet.py writes."""
    pointer = s3.get_object(Bucket=bucket, Key="models/latest_overall.txt")
    model_key = pointer["Body"].read().decode().strip()
    return model_key.replace("prophet_overall_", "metrics_overall_").replace(".pkl", ".json")


def check_threshold() -> None:
    minio = get_minio_config()
    s3 = boto3.client(
        "s3",
        endpoint_url=minio["endpoint_url"],
        aws_access_key_id=minio["access_key"],
        aws_secret_access_key=minio["secret_key"],
    )
    key = _latest_metrics_key(s3, minio["bucket"])
    obj = s3.get_object(Bucket=minio["bucket"], Key=key)
    metrics = json.loads(obj["Body"].read().decode("utf-8"))

    mae = metrics.get("mae", 0)
    mean_rev = metrics.get("mean_test_revenue", 1)
    meets = metrics.get("meets_threshold", False)

    print(f"[METRICS] MAE={mae:.2f} | Mean Test Revenue={mean_rev:.2f} | Error Rate={mae/mean_rev*100:.1f}%")

    if meets:
        print("[OK] Model meets business threshold (MAE <= 30% of mean revenue)")
    else:
        print(f"[ALERT] Model does NOT meet threshold — MAE={mae:.2f} exceeds 30% of mean revenue={mean_rev*0.30:.2f}. Manual review needed.")


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
        Key=_latest_metrics_key(s3, minio["bucket"]),
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
    schedule_interval=None,  # Triggered by lakehouse_pipeline_dag (or manually)
    catchup=False,
    is_paused_upon_creation=False,
    tags=["ml", "prophet", "training", "gold"],
) as dag:

    run_prophet_training_task = PythonOperator(
        task_id="run_prophet_training",
        python_callable=run_prophet_training,
        retries=2,
        retry_delay=timedelta(minutes=5),
    )

    check_threshold_task = PythonOperator(
        task_id="check_threshold",
        python_callable=check_threshold,
    )

    log_metrics_task = PythonOperator(
        task_id="log_metrics",
        python_callable=log_metrics,
    )

    run_prophet_training_task >> check_threshold_task >> log_metrics_task