from __future__ import annotations

from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.bash import BashOperator


def log_failure(context):
    ti = context.get("task_instance")
    dag = context.get("dag")

    dag_id = dag.dag_id if dag else "unknown_dag"
    task_id = ti.task_id if ti else "unknown_task"
    logical_date = context.get("logical_date")

    print(
        f"[FAILED] DAG={dag_id}, TASK={task_id}, LOGICAL_DATE={logical_date}. "
        "Check task logs for dbt error details."
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
    dag_id="dbt_transform_dag",
    description="Run dbt Silver and Gold transformations.",
    default_args=default_args,
    start_date=datetime(2026, 5, 27),
    schedule_interval="0 1 * * *",
    catchup=False,
    tags=["dbt", "silver", "gold", "lakehouse"],
) as dag:

    dbt_deps = BashOperator(
        task_id="dbt_deps",
        bash_command="cd /opt/dbt && dbt deps",
    )

    dbt_run_silver = BashOperator(
        task_id="dbt_run_silver",
        bash_command="cd /opt/dbt && dbt run --select staging",
    )

    dbt_test_silver = BashOperator(
        task_id="dbt_test_silver",
        bash_command="cd /opt/dbt && dbt test --select staging",
    )

    dbt_run_gold = BashOperator(
        task_id="dbt_run_gold",
        bash_command="docker exec dbt dbt run --select gold --exclude wide_sales_forecast",
    )

    dbt_test_gold = BashOperator(
        task_id="dbt_test_gold",
        bash_command="docker exec dbt dbt test --select gold --exclude wide_sales_forecast",
    )

    dbt_deps >> dbt_run_silver >> dbt_test_silver >> dbt_run_gold >> dbt_test_gold