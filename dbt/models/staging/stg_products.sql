SELECT
    CAST(product_id AS INT) AS product_id,
    TRIM(product_name) AS product_name,
    CAST(supplier_id AS INT) AS supplier_id,
    CAST(category_id AS INT) AS category_id,
    CAST(unit_price AS DECIMAL(10,2)) AS unit_price,
    CAST(units_in_stock AS INT) AS units_in_stock,
    CAST(units_on_order AS INT) AS units_on_order,
    CAST(reorder_level AS INT) AS reorder_level,
    CAST(discontinued AS INT) AS is_discontinued
FROM {{ source('bronze', 'products') }}