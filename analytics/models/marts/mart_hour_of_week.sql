-- Local ISO day of week (1 = Monday) x hour of day.
select
    extract(isodow from played_at_local)::int  as iso_dow,
    extract(hour from played_at_local)::int    as hour,
    count(*)                                   as plays,
    round(sum(duration_ms) / 60000.0, 2)       as minutes
from {{ ref('fct_plays') }}
group by 1, 2
