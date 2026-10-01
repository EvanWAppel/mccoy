-- Fails if a session ends before it starts.
select * from {{ ref('fct_listening_sessions') }}
where ended_at < started_at
