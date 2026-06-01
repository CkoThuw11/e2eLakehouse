SELECT
    CAST(order_id AS INT)                        AS order_id,
    CAST(customer_id AS STRING)                  AS customer_id,
    CAST(employee_id AS INT)                     AS employee_id,
    CAST(order_date AS DATE)                     AS order_date,
    CAST(required_date AS DATE)                  AS required_date,
    CAST(shipped_date AS DATE)                   AS shipped_date,
    CAST(ship_via AS INT)                        AS ship_via,
    CAST(freight AS DOUBLE)                      AS freight,
    TRIM(ship_name)                              AS ship_name,
    TRIM(ship_address)                           AS ship_address,
    TRIM(ship_city)                              AS ship_city,
    COALESCE(TRIM(ship_region), 'N/A')           AS ship_region,
    TRIM(ship_postal_code)                       AS ship_postal_code,
    TRIM(ship_country)                           AS ship_country,
    CURRENT_TIMESTAMP()                          AS _ingested_at
FROM {{ source('bronze', 'orders') }}