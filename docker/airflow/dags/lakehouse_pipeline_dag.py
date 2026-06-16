"""End-to-end lakehouse pipeline: bronze ingest -> dbt transform -> model retrain.

Parent DAG that orchestrates the daily refresh of the lakehouse by triggering
the existing child DAGs in dependency order:

    bronze_ingest_dag  -->  dbt_transform_dag  -->  model_retrain_dag

Each step waits for the triggered DAG to finish (and fails fast if the child
fails) so the chain stays linear and easy to debug.
"""
from __future__ import annotations

from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.trigger_dagrun import TriggerDagRunOperator


def log_failure(context):
    ti = context.get("task_instance")
    dag = context.get("dag")
    dag_id = dag.dag_id if dag else "unknown_dag"
    task_id = ti.task_id if ti else "unknown_task"
    logical_date = context.get("logical_date")
    print(
        f"[FAILED] DAG={dag_id}, TASK={task_id}, LOGICAL_DATE={logical_date}. "
        "Check the triggered child DAG run for the underlying error."
    )


default_args = {
    "owner": "dw-team",
    "depends_on_past": False,
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
    "email_on_failure": False,
    "on_failure_callback": log_failure,
}


with DAG(
    dag_id="lakehouse_pipeline_dag",
    description=(
        "End-to-end lakehouse refresh: bronze_ingest_dag -> dbt_transform_dag "
        "-> model_retrain_dag, each step waiting for the previous to finish."
    ),
    default_args=default_args,
    start_date=datetime(2026, 5, 27),
    schedule_interval="0 2 * * *",
    catchup=False,
    is_paused_upon_creation=False,
    tags=["pipeline", "bronze", "dbt", "ml", "lakehouse"],
) as dag:

    trigger_bronze_ingest = TriggerDagRunOperator(
        task_id="trigger_bronze_ingest",
        trigger_dag_id="bronze_ingest_dag",
        wait_for_completion=True,
        deferrable=True,
        poke_interval=30,
        reset_dag_run=True,
        failed_states=["failed"],
        execution_timeout=timedelta(minutes=90),
    )

    trigger_dbt_transform = TriggerDagRunOperator(
        task_id="trigger_dbt_transform",
        trigger_dag_id="dbt_transform_dag",
        wait_for_completion=True,
        deferrable=True,
        poke_interval=30,
        reset_dag_run=True,
        failed_states=["failed"],
        execution_timeout=timedelta(minutes=60),
    )

    trigger_model_retrain = TriggerDagRunOperator(
        task_id="trigger_model_retrain",
        trigger_dag_id="model_retrain_dag",
        wait_for_completion=True,
        deferrable=True,
        poke_interval=30,
        reset_dag_run=True,
        failed_states=["failed"],
        execution_timeout=timedelta(minutes=60),
    )

    trigger_bronze_ingest >> trigger_dbt_transform >> trigger_model_retrain
