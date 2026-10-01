-- One row per local calendar day with any listening.
select
    played_at_local::date                   as listen_date,
    count(*)                                as plays,
    round(sum(duration_ms) / 60000.0, 2)    as minutes,
    count(distinct primary_artist_id)       as distinct_artists
from {{ ref('fct_plays') }}
group by 1
