SELECT
    {{ dbt_utils.generate_surrogate_key(['customer_id']) }} AS customer_key,
    customer_id,
    company_name,
    city,
    country,
    region
FROM {{ ref('stg_customers') }}