{{ config(materialized='table') }}

SELECT
    {{ dbt_utils.generate_surrogate_key(['p.product_id']) }} AS product_key,
    p.product_id,
    p.product_name,
    c.category_name,
    s.company_name AS supplier_name,
    p.unit_price,
    CAST(p.is_discontinued AS BOOLEAN) AS is_discontinued
FROM {{ ref('stg_products') }} p
LEFT JOIN {{ ref('stg_categories') }} c ON p.category_id = c.category_id
LEFT JOIN {{ ref('stg_suppliers') }} s ON p.supplier_id = s.supplier_id