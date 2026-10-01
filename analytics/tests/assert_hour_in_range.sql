-- Fails if any hour bucket falls outside 0-23.
select * from {{ ref('mart_hour_of_week') }}
where hour not between 0 and 23
