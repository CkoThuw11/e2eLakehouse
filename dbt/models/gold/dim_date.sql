WITH date_spine AS (
    {{ dbt_utils.date_spine(
        datepart="day",
        start_date="cast('1996-01-01' as date)",
        end_date="cast('1999-01-01' as date)"
    ) }}
)
SELECT
    CAST(date_format(date_day, 'yyyyMMdd') AS INT) AS date_key,
    CAST(date_day AS DATE) AS full_date,
    day(date_day) AS day,
    month(date_day) AS month,
    quarter(date_day) AS quarter,
    year(date_day) AS year,
    CASE WHEN dayofweek(date_day) IN (1, 7) THEN true ELSE false END AS is_weekend
FROM date_spine
