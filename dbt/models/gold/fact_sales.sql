SELECT
    o.order_id,
    {{ dbt_utils.generate_surrogate_key(['o.order_id', 'od.product_id']) }} AS order_detail_id,
    {{ dbt_utils.generate_surrogate_key(['o.customer_id']) }} AS customer_key,
    {{ dbt_utils.generate_surrogate_key(['od.product_id']) }} AS product_key,
    {{ dbt_utils.generate_surrogate_key(['o.employee_id']) }} AS employee_key,
    CAST(date_format(o.order_date, 'yyyyMMdd') AS INT) AS date_key,
    od.quantity,
    od.unit_price,
    od.discount,
    CAST((od.quantity * od.unit_price * (1 - od.discount)) AS DOUBLE) AS line_revenue,
    o.freight
FROM {{ ref('stg_orders') }} o
JOIN {{ ref('stg_order_details') }} od ON o.order_id = od.order_id