#!/bin/sh
set -e

echo "Starting dbt container entrypoint..."

# give some time for dependent services to come up (adjust if needed)
sleep 5

echo "Running 'dbt debug' to validate configuration..."
if command -v dbt >/dev/null 2>&1; then
	dbt debug || true
else
	echo "dbt not found in image PATH"
fi

echo "dbt debug finished. Keeping container alive for interactive use."
tail -f /dev/null
