SELECT
    CAST(employee_id AS INT)              AS employee_id,
    TRIM(first_name)                      AS first_name,
    TRIM(last_name)                       AS last_name,
    TRIM(first_name) || ' ' ||
    TRIM(last_name)                       AS full_name,
    TRIM(title)                           AS title,
    CAST(birth_date AS DATE)              AS birth_date,
    CAST(hire_date AS DATE)               AS hire_date,
    TRIM(city)                            AS city,
    COALESCE(TRIM(region), 'N/A')         AS region,
    TRIM(country)                         AS country,
    CAST(reports_to AS INT)               AS reports_to,
    CURRENT_TIMESTAMP()                   AS _ingested_at
FROM {{ source('bronze', 'employees') }}