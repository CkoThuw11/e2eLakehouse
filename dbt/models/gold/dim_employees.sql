SELECT
    {{ dbt_utils.generate_surrogate_key(['employee_id']) }} AS employee_key,
    employee_id,
    CONCAT(first_name, ' ', last_name) AS full_name,
    title,
    country,
    reports_to
FROM {{ ref('stg_employees') }}