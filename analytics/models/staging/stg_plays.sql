-- Typed plays. One row per (played_at, track_id).
select
    md5(played_at::text || '|' || track_id)       as play_id,
    played_at,
    (played_at at time zone '{{ var("listening_tz") }}')
                                                  as played_at_local,
    track_id,
    payload -> 'track' ->> 'name'                 as track_name,
    (payload -> 'track' ->> 'duration_ms')::int   as duration_ms,
    payload -> 'track' -> 'album' ->> 'id'        as album_id,
    payload -> 'track' -> 'album' ->> 'name'      as album_name,
    payload -> 'track' -> 'artists' -> 0 ->> 'id' as primary_artist_id,
    payload -> 'track' -> 'artists' -> 0 ->> 'name'
                                                  as primary_artist_name,
    payload -> 'context' ->> 'type'               as context_type
from {{ source('raw', 'raw_plays') }}
