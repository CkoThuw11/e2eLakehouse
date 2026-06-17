SELECT
    CAST(category_id AS INT) AS category_id,
    TRIM(category_name) AS category_name,
    TRIM(description) AS description
FROM {{ source('bronze', 'categories') }}