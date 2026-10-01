-- Runs of consecutive local days on which an artist was played
-- (gaps-and-islands: date minus row_number is constant within a run).
with artist_days as (
    select distinct
        primary_artist_id,
        primary_artist_name,
        played_at_local::date as listen_date
    from {{ ref('fct_plays') }}
),

islands as (
    select
        *,
        listen_date - (row_number() over (
            partition by primary_artist_id order by listen_date
        ))::int as island
    from artist_days
)

select
    primary_artist_id                       as artist_id,
    max(primary_artist_name)                as artist_name,
    min(listen_date)                        as streak_start,
    max(listen_date)                        as streak_end,
    count(*)                                as streak_days
from islands
group by primary_artist_id, island
