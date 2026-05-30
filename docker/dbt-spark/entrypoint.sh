#!/bin/bash
set -e

echo "DBT container starting..."
echo "  DBT_PROFILES_DIR : ${DBT_PROFILES_DIR}"
echo "  DBT_PROJECT_DIR  : ${DBT_PROJECT_DIR}"

exec dbt "$@"