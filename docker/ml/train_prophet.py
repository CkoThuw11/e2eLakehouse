import json
import os
import tempfile
from datetime import datetime

import boto3
import joblib
import pandas as pd
import trino
from prophet import Prophet
from sklearn.metrics import mean_absolute_error, mean_squared_error


def get_env(name: str, default: str | None = None) -> str:
    value = os.getenv(name, default)
    if value is None:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def load_training_data() -> pd.DataFrame:
    trino_host = get_env("TRINO_HOST", "trino")
    trino_port = int(get_env("TRINO_PORT", "8080"))
    trino_user = get_env("TRINO_USER", "airflow")

    conn = trino.dbapi.connect(
        host=trino_host,
        port=trino_port,
        user=trino_user,
        catalog="iceberg",
        schema="gold",
    )

    query = """
        SELECT
            CAST(sale_date AS DATE) AS sale_date,
            SUM(total_revenue) AS total_revenue
        FROM iceberg.gold.wide_sales_forecast
        GROUP BY CAST(sale_date AS DATE)
        ORDER BY sale_date
    """

    df = pd.read_sql(query, conn)

    if df.empty:
        raise RuntimeError("Training data is empty. Check iceberg.gold.wide_sales_forecast.")

    df["ds"] = pd.to_datetime(df["sale_date"])
    df["y"] = pd.to_numeric(df["total_revenue"], errors="coerce").fillna(0.0)

    df = df[["ds", "y"]].sort_values("ds")

    if len(df) < 20:
        raise RuntimeError(f"Not enough rows for training. Current rows: {len(df)}")

    return df


def train_model(df: pd.DataFrame):
    split_index = int(len(df) * 0.8)

    train_df = df.iloc[:split_index]
    test_df = df.iloc[split_index:]

    model = Prophet(
        yearly_seasonality=True,
        weekly_seasonality=True,
        daily_seasonality=False,
    )

    model.fit(train_df)

    forecast = model.predict(test_df[["ds"]])

    mae = float(mean_absolute_error(test_df["y"].values, forecast["yhat"].values))
    rmse = float(mean_squared_error(test_df["y"].values, forecast["yhat"].values) ** 0.5)

    metrics = {
        "model_name": "prophet_v1",
        "trained_at": datetime.utcnow().isoformat(),
        "row_count": int(len(df)),
        "train_rows": int(len(train_df)),
        "test_rows": int(len(test_df)),
        "mae": mae,
        "rmse": rmse,
        "min_date": str(df["ds"].min().date()),
        "max_date": str(df["ds"].max().date()),
    }

    return model, metrics


def upload_to_minio(model, metrics: dict) -> None:
    endpoint_url = get_env("MINIO_ENDPOINT_URL")
    access_key = get_env("MINIO_ACCESS_KEY")
    secret_key = get_env("MINIO_SECRET_KEY")
    bucket = get_env("MINIO_BUCKET", "warehouse")

    s3 = boto3.client(
        "s3",
        endpoint_url=endpoint_url,
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
    )

    with tempfile.TemporaryDirectory() as tmpdir:
        model_path = os.path.join(tmpdir, "prophet_v1.pkl")
        metrics_path = os.path.join(tmpdir, "prophet_v1_metrics.json")

        joblib.dump(model, model_path)

        with open(metrics_path, "w", encoding="utf-8") as f:
            json.dump(metrics, f, indent=2)

        s3.upload_file(model_path, bucket, "models/prophet_v1.pkl")
        s3.upload_file(metrics_path, bucket, "models/prophet_v1_metrics.json")

    print("Uploaded model to s3://warehouse/models/prophet_v1.pkl")
    print("Uploaded metrics to s3://warehouse/models/prophet_v1_metrics.json")
    print(json.dumps(metrics, indent=2))


def main():
    df = load_training_data()
    model, metrics = train_model(df)
    upload_to_minio(model, metrics)


if __name__ == "__main__":
    main()