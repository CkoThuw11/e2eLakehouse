SELECT
    CAST(supplier_id AS INT) AS supplier_id,
    TRIM(company_name) AS company_name,
    TRIM(contact_name) AS contact_name,
    TRIM(contact_title) AS contact_title,
    TRIM(city) AS city,
    TRIM(region) AS region,
    TRIM(postal_code) AS postal_code,
    TRIM(country) AS country,
    TRIM(phone) AS phone
FROM {{ source('bronze', 'suppliers') }}