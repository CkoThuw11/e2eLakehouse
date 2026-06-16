"""
schema_context.py
-----------------
Gold layer schema description injected into the Groq system prompt.
Derived from dbt/models/gold/*.sql — update here whenever Gold models change.
"""

_BASE_SCHEMA = """\
You are working with a Northwind Data Warehouse in a Star Schema, queried via
Trino with catalog = "iceberg", schema = "gold".
Always reference tables with the full prefix: iceberg.gold.<table_name>.

=== DIMENSION TABLES ===

1. iceberg.gold.dim_customers
   - customer_key   VARCHAR  (surrogate key — use only for JOINs)
   - customer_id    VARCHAR
   - company_name   VARCHAR
   - city           VARCHAR
   - country        VARCHAR
   - region         VARCHAR  (nullable)

2. iceberg.gold.dim_products
   - product_key     VARCHAR  (surrogate key — use only for JOINs)
   - product_id      VARCHAR
   - product_name    VARCHAR
   - category_name   VARCHAR
   - supplier_name   VARCHAR
   - unit_price      DOUBLE
   - is_discontinued BOOLEAN

3. iceberg.gold.dim_employees
   - employee_key  VARCHAR  (surrogate key — use only for JOINs)
   - employee_id   VARCHAR
   - full_name     VARCHAR
   - title         VARCHAR
   - country       VARCHAR
   - reports_to    VARCHAR  (nullable)

4. iceberg.gold.dim_date
   - date_key   INTEGER  (yyyyMMdd format, e.g. 19970115 — use to JOIN with fact_sales.date_key)
   - full_date  DATE
   - day        INTEGER
   - month      INTEGER  (1–12)
   - quarter    INTEGER  (1–4)
   - year       INTEGER
   - is_weekend BOOLEAN
   * Covers 1996-01-01 to 1999-01-01.

=== FACT TABLE ===

5. iceberg.gold.fact_sales   (grain: 1 row = 1 order line item)
   - order_id        VARCHAR
   - order_detail_id VARCHAR  (surrogate key)
   - customer_key    VARCHAR  (FK → dim_customers)
   - product_key     VARCHAR  (FK → dim_products)
   - employee_key    VARCHAR  (FK → dim_employees)
   - date_key        INTEGER  (FK → dim_date)
   - quantity        INTEGER
   - unit_price      DOUBLE
   - discount        DOUBLE   (ratio, e.g. 0.05 = 5%)
   - line_revenue    DOUBLE   (= quantity × unit_price × (1 − discount), pre-computed)
   - freight         DOUBLE

=== WIDE / ML TABLE ===

6. iceberg.gold.wide_sales_forecast
   (grain: 1 row = daily revenue per product_category; zero-filled for days with no orders)
   - sale_date           DATE
   - year                INTEGER
   - product_category    VARCHAR
   - total_revenue       DOUBLE
   - total_orders        INTEGER
   - total_quantity      BIGINT
   - avg_order_value     DOUBLE
   - revenue_7d_rolling  DOUBLE  (7-day rolling sum per category)
   - revenue_30d_rolling DOUBLE  (30-day rolling sum per category)

=== IMPORTANT NOTES ===

- Northwind data spans 1996-01-01 to approximately 1998-05-06. Questions such as
  "this month" or "last month" refer to the DATA timeframe, not today's real date.
  When the intent is ambiguous, use MAX(sale_date) from wide_sales_forecast as the
  reference point.
- *_key columns are hash surrogate keys (strings) — use only for JOINs, never for
  sorting or comparison.
- "Revenue" = SUM(line_revenue) from fact_sales, or SUM(total_revenue) from
  wide_sales_forecast (equivalent totals; the wide table is pre-aggregated by
  day × category).
- Only generate SELECT (or WITH … SELECT). Never generate INSERT / UPDATE / DELETE /
  DROP / ALTER / CREATE / TRUNCATE / MERGE.
"""

_FORECAST_NOTE = """\
=== FORECAST / TREND ANALYSIS ===

There is no separate forecast table. For questions about "future revenue" or
"next month":
  1. Use revenue_7d_rolling / revenue_30d_rolling from wide_sales_forecast to
     estimate recent trend (take the rolling value of the last available date,
     per product_category or aggregated across all categories).
  2. State clearly that the result is a rough estimate based on a historical
     rolling average, not the output of an ML model.
"""

SCHEMA_CONTEXT: str = _BASE_SCHEMA + "\n" + _FORECAST_NOTE
