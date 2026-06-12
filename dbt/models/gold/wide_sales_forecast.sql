{{ config(
    materialized='table',
    file_format='iceberg',
    schema='gold'
) }}

WITH all_dates AS (
    SELECT full_date, year
    FROM {{ ref('dim_date') }}
),

all_categories AS (
    SELECT DISTINCT category_name
    FROM {{ ref('dim_products') }}
    WHERE category_name IS NOT NULL
),

date_category_spine AS (
    SELECT
        d.full_date AS sale_date,
        d.year,
        c.category_name AS product_category
    FROM all_dates d
    CROSS JOIN all_categories c
),

daily_sales AS (
    SELECT
        CAST(dd.full_date AS DATE) AS sale_date,
        dp.category_name AS product_category,
        SUM(fs.line_revenue) AS total_revenue,
        COUNT(DISTINCT fs.order_id) AS total_orders,
        SUM(fs.quantity) AS total_quantity,
        CASE
            WHEN COUNT(DISTINCT fs.order_id) = 0 THEN 0
            ELSE SUM(fs.line_revenue) / COUNT(DISTINCT fs.order_id)
        END AS avg_order_value
    FROM {{ ref('fact_sales') }} fs
    JOIN {{ ref('dim_date') }} dd
        ON fs.date_key = dd.date_key
    JOIN {{ ref('dim_products') }} dp
        ON fs.product_key = dp.product_key
    GROUP BY 1, 2
),

filled AS (
    SELECT
        sp.sale_date,
        sp.year,
        sp.product_category,
        COALESCE(ds.total_revenue, 0.0) AS total_revenue,
        COALESCE(ds.total_orders, 0) AS total_orders,
        COALESCE(ds.total_quantity, 0) AS total_quantity,
        COALESCE(ds.avg_order_value, 0.0) AS avg_order_value
    FROM date_category_spine sp
    LEFT JOIN daily_sales ds
        ON sp.sale_date = ds.sale_date
        AND sp.product_category = ds.product_category
),

final AS (
    SELECT
        sale_date, 
        year,
        product_category,
        total_revenue,
        total_orders,
        total_quantity,
        avg_order_value,

        SUM(total_revenue) OVER (
            PARTITION BY product_category
            ORDER BY sale_date
            ROWS BETWEEN 6 PRECEDING AND CURRENT ROW
        ) AS revenue_7d_rolling,

        SUM(total_revenue) OVER (
            PARTITION BY product_category
            ORDER BY sale_date
            ROWS BETWEEN 29 PRECEDING AND CURRENT ROW
        ) AS revenue_30d_rolling,

        year

    FROM filled
)

SELECT * FROM final