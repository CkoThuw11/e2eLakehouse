SELECT
    CAST(customer_id AS STRING)           AS customer_id,
    TRIM(company_name)                    AS company_name,
    TRIM(contact_name)                    AS contact_name,
    TRIM(contact_title)                   AS contact_title,
    TRIM(address)                         AS address,
    TRIM(city)                            AS city,
    COALESCE(TRIM(region), 'N/A')         AS region,
    TRIM(postal_code)                     AS postal_code,
    TRIM(country)                         AS country,
    TRIM(phone)                           AS phone,
    CURRENT_TIMESTAMP()                   AS _ingested_at
FROM {{ source('bronze', 'customers') }}