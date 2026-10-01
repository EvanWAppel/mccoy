-- Track dimension from the most recent payload seen for each track.
select distinct on (track_id)
    track_id,
    payload -> 'track' ->> 'name'                 as track_name,
    (payload -> 'track' ->> 'duration_ms')::int   as duration_ms,
    payload -> 'track' -> 'album' ->> 'id'        as album_id,
    payload -> 'track' -> 'album' ->> 'name'      as album_name,
    payload -> 'track' -> 'artists' -> 0 ->> 'id' as primary_artist_id
from {{ source('raw', 'raw_plays') }}
order by track_id, played_at desc
