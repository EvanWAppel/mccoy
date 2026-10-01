-- Plays with a session id: a gap longer than session_gap_minutes since
-- the previous play starts a new session.
with ordered as (
    select
        *,
        lag(played_at) over (order by played_at) as prev_played_at
    from {{ ref('stg_plays') }}
),

flagged as (
    select
        *,
        case
            when prev_played_at is null
              or played_at - prev_played_at
                 > interval '{{ var("session_gap_minutes") }} minutes'
            then 1 else 0
        end as is_session_start
    from ordered
)

select
    play_id,
    played_at,
    played_at_local,
    track_id,
    track_name,
    duration_ms,
    album_name,
    primary_artist_id,
    primary_artist_name,
    sum(is_session_start) over (order by played_at) as session_id
from flagged
