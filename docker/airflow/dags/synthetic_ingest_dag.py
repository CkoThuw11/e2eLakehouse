"""Append synthetic Northwind data to bronze, then refresh silver/gold via dbt
and (optionally) retrain the Prophet model.

Manual / on-demand DAG — does NOT run on a schedule. Trigger it from the UI
or CLI whenever you want a fresh batch of synthetic days to flow through the
warehouse.
"""
from __future__ import annotations

import os
import subprocess
import sys
from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.operators.trigger_dagrun import TriggerDagRunOperator


def log_failure(context):
    ti = context.get("task_instance")
    dag = context.get("dag")
    print(f"[FAILED] DAG={dag.dag_id if dag else '?'} TASK={ti.task_id if ti else '?'}")


def run_spark_script(script_path: str, extra_env: dict | None = None) -> None:
    spark_home = "/home/airflow/.local/lib/python3.11/site-packages/pyspark"
    env = os.environ.copy()
    env.update({
        "SPARK_CONF_DIR": "/opt/spark-conf",
        "JAVA_HOME": "/usr/lib/jvm/java-17-openjdk-amd64",
        "SPARK_HOME": spark_home,
        "PYSPARK_PYTHON": sys.executable,
        "PYSPARK_DRIVER_PYTHON": sys.executable,
    })
    if extra_env:
        env.update({k: str(v) for k, v in extra_env.items()})

    print(f"[INFO] Running spark script: {script_path}")
    result = subprocess.run(
        [sys.executable, script_path],
        env=env,
        capture_output=False,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(f"{script_path} failed (exit {result.returncode})")


def ingest_synthetic(**context) -> None:
    # Operators can pass overrides via DAG run conf: {"days": 60, "per_day": 20}
    conf = (context.get("dag_run") and context["dag_run"].conf) or {}
    extra_env = {}
    if "days" in conf:
        extra_env["SYNTHETIC_DAYS"] = conf["days"]
    if "per_day" in conf:
        extra_env["SYNTHETIC_ORDERS_DAY"] = conf["per_day"]
    if "seed" in conf:
        extra_env["SYNTHETIC_SEED"] = conf["seed"]
    run_spark_script("/opt/spark-app/ingest_synthetic.py", extra_env=extra_env)


default_args = {
    "owner": "dw-team",
    "depends_on_past": False,
    "retries": 1,
    "retry_delay": timedelta(minutes=2),
    "email_on_failure": False,
    "on_failure_callback": log_failure,
}


with DAG(
    dag_id="synthetic_ingest_dag",
    description=(
        "Append synthetic orders to bronze (incremental), then refresh dbt "
        "silver/gold and optionally retrain the Prophet model."
    ),
    default_args=default_args,
    start_date=datetime(2026, 5, 27),
    schedule_interval=None,            # manual / on-demand
    catchup=False,
    tags=["spark", "bronze", "synthetic", "incremental"],
) as dag:

    append_synthetic = PythonOperator(
        task_id="append_synthetic_to_bronze",
        python_callable=ingest_synthetic,
        execution_timeout=timedelta(minutes=30),
    )

    trigger_dbt = TriggerDagRunOperator(
        task_id="trigger_dbt_transform",
        trigger_dag_id="dbt_transform_dag",
        wait_for_completion=True,
        poke_interval=15,
        reset_dag_run=True,
    )

    trigger_retrain = TriggerDagRunOperator(
        task_id="trigger_model_retrain",
        trigger_dag_id="model_retrain_dag",
        wait_for_completion=True,
        poke_interval=15,
        reset_dag_run=True,
    )

    append_synthetic >> trigger_dbt >> trigger_retrain
