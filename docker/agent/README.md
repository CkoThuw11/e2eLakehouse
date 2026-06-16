# Groq Agent — Text-to-SQL for the Northwind Gold Layer

AI agent that accepts a natural-language question, generates SQL via the Groq API
(LLaMA 3.3 70B), validates it, executes it on Trino (`iceberg.gold`), and returns
a plain-language answer.

## Structure

```
docker/agent/
├── Dockerfile
├── .dockerignore
├── .env.example
├── compose.snippet.yaml
├── requirements.txt
├── main.py               ← CLI entrypoint
├── agent/                ← source package
│   ├── __init__.py
│   ├── config.py         — TrinoConfig / GroqConfig from env vars
│   ├── trino_client.py   — run_trino_query(sql) → DataFrame
│   ├── sql_guard.py      — validate SQL: SELECT/WITH only, single statement
│   ├── schema_context.py — Gold schema description injected into system prompt
│   └── groq_agent.py     — GroqAgent: NL → SQL → Trino → NL answer
└── tests/
    ├── test_sql_guard.py   — offline unit tests for sql_guard
    └── test_agent_flow.py  — flow tests with mocked Groq + Trino
```

## Pipeline (`GroqAgent.ask`)

1. Receive natural-language question.
2. `generate_sql()` — send question + schema context to Groq → receive SQL.
3. `validate_select_only()` — reject anything that isn't a single `SELECT`/`WITH`.
4. `run_trino_query()` — execute SQL on Trino → `pandas.DataFrame`.
5. `format_answer()` — send question + SQL + result to Groq → natural-language answer.
6. Return `AgentResult`.

If step 3 or 4 fails due to **bad SQL**, the agent feeds the error back to Groq and
retries once (`max_sql_retries=1`). If the failure is a **connection/timeout error**,
it stops immediately — retrying the same SQL won't help.

## Setup

### Option A — Docker (recommended)

1. Add the `groq-agent` service from `compose.snippet.yaml` to `docker-compose.yaml`.
2. Add your Groq API key to the root `.env`:
   ```
   GROQ_API_KEY=<your key from https://console.groq.com>
   ```
3. Build and run:
   ```bash
   docker compose build groq-agent
   docker compose up -d trino minio hive-metastore   # if not already running
   docker compose run --rm groq-agent
   ```

### Option B — Local venv

```bash
cd docker/agent
pip install -r requirements.txt
cp .env.example .env   # fill in GROQ_API_KEY and verify TRINO_HOST/PORT
python main.py
```

**Trino host/port note:**
- Running from the **host machine**: `TRINO_HOST=localhost`, `TRINO_PORT=8090`
- Running **inside a Docker container** on `data-network`: `TRINO_HOST=trino`, `TRINO_PORT=8080`

## Running

```bash
# 5 sample questions (Task 11 deliverable)
docker compose run --rm groq-agent

# Single question
docker compose run --rm groq-agent python main.py -q "Doanh thu theo tháng trong năm gần nhất?"

# Interactive mode
docker compose run --rm groq-agent python main.py --interactive

# Run tests
docker compose run --rm groq-agent pytest tests/ -v
```

## Sample Questions

1. Top 5 sản phẩm bán chạy nhất tháng trước là gì?
2. Doanh thu theo tháng trong năm gần nhất có dữ liệu là bao nhiêu?
3. Khách hàng nào có giá trị đơn hàng trung bình cao nhất?
4. Category nào tăng trưởng mạnh nhất so với tháng trước?
5. Xu hướng doanh thu 30 ngày gần nhất là tăng hay giảm, và dự báo sơ bộ cho 30 ngày tới?

> Northwind data spans 1996–1998. "Last month" / "this year" are resolved against
> `MAX(sale_date)` in `wide_sales_forecast`, not today's date.

## SQL Safety

Every Groq-generated SQL must pass `sql_guard.validate_select_only()`:
- Single statement only — no `;` mid-query.
- Must start with `SELECT` or `WITH`.
- Must not contain: `INSERT UPDATE DELETE DROP ALTER CREATE TRUNCATE MERGE
  GRANT REVOKE CALL COPY EXECUTE REPLACE VACUUM ANALYZE`.

Word-boundary matching prevents false positives on column names like `created_at`.

## Testing

```bash
pytest tests/ -v
```

- `test_sql_guard.py` — 12 offline tests covering all validation rules.
- `test_agent_flow.py` — 6 flow tests (success, retry on bad SQL, retry on Trino
  syntax error, exhausted retries, connection error stops immediately, empty result).
  No `GROQ_API_KEY` or live Trino required.

## Troubleshooting

| Error | Likely cause |
|---|---|
| `Configuration error: GROQ_API_KEY is not set` | Missing `.env` (Option B) or `GROQ_API_KEY` not in root `.env` (Option A). |
| `Unable to connect to Trino` | Docker: check `TRINO_HOST=trino` / `TRINO_PORT=8080`; ensure `trino` service is up. Local: check `TRINO_HOST=localhost` / `TRINO_PORT=8090`. |
| `network data-network not found` | Run `docker compose up -d` for at least one other service first to create the network. |
| Trino syntax error after retry | Groq generated the wrong table/column name — verify `agent/schema_context.py` matches the current dbt Gold models. |
