"""Data-loading helpers for the Northwind Lakehouse dashboard.

All Trino queries and MinIO model lookups live here so the main app file
stays focused on page layout. Functions are cached with Streamlit's standard
cache decorators; clearing those caches forces the next read to hit Trino /
MinIO again.
"""
from __future__ import annotations

import json
import os
import pickle
from datetime import date
from typing import Optional

import boto3
import pandas as pd
import streamlit as st
from botocore.client import Config
from trino.dbapi import connect


_T_HOST = os.getenv("TRINO_HOST", "localhost")
_T_PORT = int(os.getenv("TRINO_PORT", "8090"))
_T_USER = os.getenv("TRINO_USER", "streamlit_dashboard")


@st.cache_data(ttl=3600, show_spinner=False)
def run_query(sql: str) -> pd.DataFrame:
    conn = connect(
        host=_T_HOST, port=_T_PORT, user=_T_USER,
        catalog="iceberg", schema="gold",
        http_scheme="http", request_timeout=60,
    )
    try:
        cur = conn.cursor()
        cur.execute(sql)
        rows = cur.fetchall()
        cols = [d[0] for d in (cur.description or [])]
        return pd.DataFrame(rows, columns=cols)
    finally:
        try:
            conn.close()
        except Exception:
            pass


def qry(sql: str, msg: str = "Loading…") -> Optional[pd.DataFrame]:
    try:
        with st.spinner(msg):
            return run_query(sql)
    except Exception as exc:
        st.error(f"Query error: {exc}")
        return None


@st.cache_data(ttl=3600, show_spinner=False)
def date_bounds() -> tuple[date, date]:
    try:
        df = run_query(
            "SELECT MIN(sale_date) mn, MAX(sale_date) mx "
            "FROM iceberg.gold.wide_sales_forecast WHERE total_revenue > 0"
        )
        if df.empty:
            raise ValueError
        mn, mx = df["mn"].iloc[0], df["mx"].iloc[0]
        mn = mn.date() if hasattr(mn, "date") else mn
        mx = mx.date() if hasattr(mx, "date") else mx
        return date(mn.year, mn.month, mn.day), date(mx.year, mx.month, mx.day)
    except Exception:
        return date(1996, 7, 4), date(1998, 5, 6)


def _minio_client():
    endpoint = os.getenv("MINIO_ENDPOINT", "http://minio:9000")
    access   = os.getenv("MINIO_ACCESS_KEY", "")
    secret   = os.getenv("MINIO_SECRET_KEY", "")
    return boto3.client(
        "s3",
        endpoint_url=endpoint,
        aws_access_key_id=access,
        aws_secret_access_key=secret,
        config=Config(signature_version="s3v4", s3={"addressing_style": "path"}),
    )


@st.cache_resource(ttl=3600, show_spinner=False)
def load_prophet_model():
    """Load latest Prophet model from MinIO. Returns (model, metrics) or (None, error_dict)."""
    try:
        bucket = "warehouse"
        s3 = _minio_client()

        pointer_obj = s3.get_object(Bucket=bucket, Key="models/latest_overall.txt")
        model_key   = pointer_obj["Body"].read().decode().strip()
        metrics_key = model_key.replace("prophet_overall_", "metrics_overall_").replace(".pkl", ".json")

        model_obj  = s3.get_object(Bucket=bucket, Key=model_key)
        model      = pickle.loads(model_obj["Body"].read())

        metrics_obj = s3.get_object(Bucket=bucket, Key=metrics_key)
        metrics     = json.loads(metrics_obj["Body"].read().decode())

        return model, metrics
    except Exception as exc:
        return None, {"error": str(exc)}


@st.cache_data(ttl=600, show_spinner=False)
def load_training_history() -> pd.DataFrame:
    """List every metrics_overall_*.json in MinIO and return them as a DataFrame
    ordered by trained_at. Empty DataFrame if nothing found or on error."""
    try:
        bucket = "warehouse"
        s3 = _minio_client()

        paginator = s3.get_paginator("list_objects_v2")
        rows: list[dict] = []
        for page in paginator.paginate(Bucket=bucket, Prefix="models/metrics_overall_"):
            for obj in page.get("Contents", []) or []:
                key = obj["Key"]
                if not key.endswith(".json"):
                    continue
                try:
                    body = s3.get_object(Bucket=bucket, Key=key)["Body"].read()
                    payload = json.loads(body.decode())
                    payload["_key"]  = key
                    payload["_size"] = obj.get("Size", 0)
                    rows.append(payload)
                except Exception:
                    continue

        if not rows:
            return pd.DataFrame()

        df = pd.DataFrame(rows)
        if "trained_at" in df.columns:
            df["trained_at"] = pd.to_datetime(df["trained_at"], errors="coerce")
            df = df.sort_values("trained_at").reset_index(drop=True)
        return df
    except Exception:
        return pd.DataFrame()


def refresh_everything() -> None:
    """Clear cached query + model data so the next render hits Trino/MinIO again."""
    st.cache_data.clear()
    st.cache_resource.clear()
