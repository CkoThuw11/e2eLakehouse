SELECT
    CAST(order_id AS INT)      AS order_id,
    CAST(product_id AS INT)    AS product_id,
    CAST(unit_price AS DECIMAL(10,2))  AS unit_price,
    CAST(quantity AS INT)              AS quantity,
    CAST(discount AS DOUBLE)           AS discount,
    CAST(unit_price AS DECIMAL(10,2)) * quantity * (1 - discount) AS line_revenue,
    CAST(order_id AS STRING) || '-' || CAST(product_id AS STRING) AS order_detail_id,
    CURRENT_TIMESTAMP()                                           AS _ingested_at
FROM {{ source('bronze', 'order_details') }}