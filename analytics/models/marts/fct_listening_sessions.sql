select
    session_id,
    min(played_at)                          as started_at,
    max(played_at)                          as ended_at,
    count(*)                                as plays,
    round(sum(duration_ms) / 60000.0, 2)    as minutes,
    count(distinct primary_artist_id)       as distinct_artists
from {{ ref('fct_plays') }}
group by session_id
