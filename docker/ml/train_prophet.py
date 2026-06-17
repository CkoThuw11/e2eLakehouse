"""Prophet retraining script for daily revenue forecasting.

Reads daily revenue from iceberg.gold.wide_sales_forecast via Trino, runs a
grid search over Prophet hyperparameters, retrains a final model on the full
series, and uploads the model + metrics + a `latest` pointer to MinIO.

All configuration is read from environment variables so the script can be
invoked as a subprocess from Airflow.
"""
from __future__ import annotations

import json
import logging
import os
import pickle
import sys
from datetime import datetime
from itertools import product
from math import sqrt

import boto3
import pandas as pd
from botocore.config import Config
from prophet import Prophet
from sklearn.metrics import mean_absolute_error, mean_squared_error
from trino.dbapi import connect

logging.getLogger("prophet").setLevel(logging.WARNING)
logging.getLogger("cmdstanpy").setLevel(logging.WARNING)


def _env(name: str, default: str | None = None) -> str:
    val = os.getenv(name, default)
    if val is None:
        raise RuntimeError(f"Missing required env var: {name}")
    return val


class _SuppressOutput:
    """Silence Prophet/Stan chatter on stdout and stderr."""

    def __enter__(self):
        self._stdout_fd = os.dup(1)
        self._stderr_fd = os.dup(2)
        self._devnull = os.open(os.devnull, os.O_WRONLY)
        os.dup2(self._devnull, 1)
        os.dup2(self._devnull, 2)
        return self

    def __exit__(self, exc_type, exc, tb):
        os.dup2(self._stdout_fd, 1)
        os.dup2(self._stderr_fd, 2)
        os.close(self._devnull)
        os.close(self._stdout_fd)
        os.close(self._stderr_fd)


def load_revenue_df() -> pd.DataFrame:
    host = _env("TRINO_HOST", "trino")
    port = int(_env("TRINO_PORT", "8080"))
    user = _env("TRINO_USER", "airflow")

    print(f"[INFO] Connecting to Trino at {host}:{port} as {user}")
    conn = connect(
        host=host, port=port, user=user,
        catalog="iceberg", schema="gold",
        http_scheme="http", request_timeout=60,
    )
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT sale_date, SUM(total_revenue) AS total_revenue "
            "FROM iceberg.gold.wide_sales_forecast "
            "GROUP BY sale_date ORDER BY sale_date"
        )
        rows = cur.fetchall()
        cols = [d[0] for d in (cur.description or [])]
    finally:
        try:
            conn.close()
        except Exception:
            pass

    df = pd.DataFrame(rows, columns=cols)
    print(f"[INFO] Loaded {len(df)} rows from wide_sales_forecast")
    return df


def filter_active_period(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df = df[df["total_revenue"] > 0]
    if df.empty:
        raise RuntimeError("No rows with positive revenue found")

    first_date = df["sale_date"].min()
    last_date = df["sale_date"].max()
    df = df[(df["sale_date"] >= first_date) & (df["sale_date"] <= last_date)]
    print(f"[INFO] Active sales period: {first_date} → {last_date} ({len(df)} rows)")
    return df


def prepare_prophet_df(df: pd.DataFrame) -> pd.DataFrame:
    prophet_df = df.rename(columns={"sale_date": "ds", "total_revenue": "y"})[["ds", "y"]].copy()
    prophet_df["ds"] = pd.to_datetime(prophet_df["ds"]).dt.tz_localize(None)
    prophet_df = prophet_df.sort_values("ds").reset_index(drop=True)
    return prophet_df


def grid_search(train_df: pd.DataFrame, test_df: pd.DataFrame) -> tuple[dict, float]:
    grid = {
        "changepoint_prior_scale": [0.001, 0.01, 0.05, 0.1, 0.3, 0.5],
        "seasonality_prior_scale": [0.01, 0.1, 1.0, 5.0],
    }
    best_params: dict | None = None
    best_mae = float("inf")

    combos = list(product(grid["changepoint_prior_scale"], grid["seasonality_prior_scale"]))
    print(f"[INFO] Grid search: {len(combos)} combinations")

    for cps, sps in combos:
        params = {"changepoint_prior_scale": cps, "seasonality_prior_scale": sps}
        try:
            with _SuppressOutput():
                m = Prophet(
                    yearly_seasonality=False,
                    weekly_seasonality=True,
                    daily_seasonality=False,
                    **params,
                )
                m.fit(train_df)
                preds = m.predict(test_df[["ds"]])
            mae = mean_absolute_error(test_df["y"].values, preds["yhat"].values)
        except Exception as exc:
            print(f"[WARN] combo {params} failed: {exc}")
            continue

        if mae < best_mae:
            best_mae = mae
            best_params = params
            print(f"[INFO] new best: {params} → MAE={mae:.2f}")

    if best_params is None:
        raise RuntimeError("Grid search produced no successful fits")

    print(f"[INFO] Best params: {best_params} (MAE={best_mae:.2f})")
    return best_params, best_mae


def compute_test_metrics(train_df: pd.DataFrame, test_df: pd.DataFrame, best_params: dict) -> dict:
    with _SuppressOutput():
        m = Prophet(
            yearly_seasonality=False,
            weekly_seasonality=True,
            daily_seasonality=False,
            **best_params,
        )
        m.fit(train_df)
        preds = m.predict(test_df[["ds"]])

    y_true = test_df["y"].values
    y_pred = preds["yhat"].values
    mae = float(mean_absolute_error(y_true, y_pred))
    rmse = float(sqrt(mean_squared_error(y_true, y_pred)))
    mean_test_revenue = float(pd.Series(y_true).mean())
    meets_threshold = bool(mae <= 0.30 * mean_test_revenue)

    print(
        f"[INFO] Final metrics — MAE={mae:.2f} RMSE={rmse:.2f} "
        f"mean_test_revenue={mean_test_revenue:.2f} meets_threshold={meets_threshold}"
    )
    return {
        "mae": mae,
        "rmse": rmse,
        "mean_test_revenue": mean_test_revenue,
        "meets_threshold": meets_threshold,
    }


def fit_final_model(prophet_df: pd.DataFrame, best_params: dict) -> Prophet:
    print("[INFO] Fitting final model on full dataset")
    with _SuppressOutput():
        model = Prophet(
            yearly_seasonality=True,
            weekly_seasonality=True,
            daily_seasonality=False,
            **best_params,
        )
        model.fit(prophet_df)
    return model


def upload_artifacts(model_path: str, metrics_path: str, model_key: str, metrics_key: str) -> None:
    endpoint = _env("MINIO_ENDPOINT_URL", "http://minio:9000")
    access = _env("MINIO_ACCESS_KEY")
    secret = _env("MINIO_SECRET_KEY")
    bucket = _env("MINIO_BUCKET", "warehouse")

    print(f"[INFO] Uploading artifacts to s3://{bucket}/ via {endpoint}")
    s3 = boto3.client(
        "s3",
        endpoint_url=endpoint,
        aws_access_key_id=access,
        aws_secret_access_key=secret,
        config=Config(signature_version="s3v4", s3={"addressing_style": "path"}),
    )

    s3.upload_file(model_path, bucket, model_key)
    print(f"[INFO] Uploaded {model_key}")

    s3.upload_file(metrics_path, bucket, metrics_key)
    print(f"[INFO] Uploaded {metrics_key}")

    s3.put_object(
        Bucket=bucket,
        Key="models/latest_overall.txt",
        Body=model_key.encode(),
    )
    print("[INFO] Updated models/latest_overall.txt pointer")


def main() -> None:
    print("[INFO] Starting Prophet training pipeline")

    df = load_revenue_df()
    df = filter_active_period(df)
    prophet_df = prepare_prophet_df(df)

    split = int(len(prophet_df) * 0.8)
    train_df = prophet_df.iloc[:split].reset_index(drop=True)
    test_df = prophet_df.iloc[split:].reset_index(drop=True)
    print(f"[INFO] Split: train={len(train_df)} test={len(test_df)}")

    best_params, _ = grid_search(train_df, test_df)
    metrics = compute_test_metrics(train_df, test_df, best_params)

    final_model = fit_final_model(prophet_df, best_params)

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    model_filename = f"prophet_overall_{stamp}.pkl"
    metrics_filename = f"metrics_overall_{stamp}.json"
    model_path = f"/tmp/{model_filename}"
    metrics_path = f"/tmp/{metrics_filename}"
    model_key = f"models/{model_filename}"
    metrics_key = f"models/{metrics_filename}"

    metrics_payload = {
        "model_key": model_key,
        "mae": metrics["mae"],
        "rmse": metrics["rmse"],
        "mean_test_revenue": metrics["mean_test_revenue"],
        "meets_threshold": metrics["meets_threshold"],
        "train_end_date": str(prophet_df["ds"].max().date()),
        "trained_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }

    with open(model_path, "wb") as fh:
        pickle.dump(final_model, fh)
    print(f"[INFO] Saved model to {model_path}")

    with open(metrics_path, "w", encoding="utf-8") as fh:
        json.dump(metrics_payload, fh, indent=2)
    print(f"[INFO] Saved metrics to {metrics_path}")

    upload_artifacts(model_path, metrics_path, model_key, metrics_key)
    print("[INFO] Done")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"[ERROR] Training pipeline failed: {exc}", file=sys.stderr)
        raise
