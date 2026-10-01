-- Artist dimension: every credited artist on any played track.
select distinct on (artist ->> 'id')
    artist ->> 'id'   as artist_id,
    artist ->> 'name' as artist_name
from {{ source('raw', 'raw_plays') }},
    jsonb_array_elements(payload -> 'track' -> 'artists') as artist
where artist ->> 'id' is not null
order by artist ->> 'id', played_at desc
