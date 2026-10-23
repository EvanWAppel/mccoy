-- Fixture database for the Ask Your Listening evals (XX-05).
--
-- A hand-built `marts` schema with the same tables and columns as the
-- dbt marts (analytics/models/marts), filled with three listening
-- sessions on Sun 18 - Tue 20 Oct 2026 (America/Los_Angeles, UTC-7).
-- The aggregate marts are written to agree with fct_plays, so the
-- expected answers in cases.json can be checked by hand:
--   plays per artist: Bon Iver 4, Low 3, Big Thief 2, Phoebe Bridgers 1
--   sessions: 1 (Sun 21:00, 3 plays), 2 (Mon 08:00, 3), 3 (Tue 21:30, 4)
-- tests/evals/test_evals.py checks the columns against ask.MARTS_SCHEMA.

create schema marts;

create table marts.fct_plays (
    play_id text primary key,
    played_at timestamptz not null,
    played_at_local timestamp not null,
    track_id text not null,
    track_name text not null,
    duration_ms int not null,
    album_name text,
    primary_artist_id text not null,
    primary_artist_name text not null,
    session_id bigint not null
);

create table marts.fct_listening_sessions (
    session_id bigint primary key,
    started_at timestamptz not null,
    ended_at timestamptz not null,
    plays bigint not null,
    minutes numeric not null,
    distinct_artists bigint not null
);

create table marts.mart_daily_listening (
    listen_date date primary key,
    plays bigint not null,
    minutes numeric not null,
    distinct_artists bigint not null
);

create table marts.mart_hour_of_week (
    iso_dow int not null,
    hour int not null,
    plays bigint not null,
    minutes numeric not null,
    primary key (iso_dow, hour)
);

create table marts.mart_artist_streaks (
    artist_id text not null,
    artist_name text not null,
    streak_start date not null,
    streak_end date not null,
    streak_days bigint not null
);

insert into marts.fct_plays values
    ('p01', '2026-10-19 04:00:00+00', '2026-10-18 21:00:00',
     't_holocene', 'Holocene', 336000, 'Bon Iver, Bon Iver',
     'a_boniver', 'Bon Iver', 1),
    ('p02', '2026-10-19 04:06:00+00', '2026-10-18 21:06:00',
     't_restacks', 'Re: Stacks', 401000, 'For Emma, Forever Ago',
     'a_boniver', 'Bon Iver', 1),
    ('p03', '2026-10-19 04:13:00+00', '2026-10-18 21:13:00',
     't_lies', 'Lies', 263000, 'Ones and Sixes',
     'a_low', 'Low', 1),
    ('p04', '2026-10-19 15:00:00+00', '2026-10-19 08:00:00',
     't_holocene', 'Holocene', 336000, 'Bon Iver, Bon Iver',
     'a_boniver', 'Bon Iver', 2),
    ('p05', '2026-10-19 15:06:00+00', '2026-10-19 08:06:00',
     't_not', 'Not', 371000, 'Two Hands',
     'a_bigthief', 'Big Thief', 2),
    ('p06', '2026-10-19 15:12:00+00', '2026-10-19 08:12:00',
     't_dayslike', 'Days Like These', 300000, 'Double Negative',
     'a_low', 'Low', 2),
    ('p07', '2026-10-21 04:30:00+00', '2026-10-20 21:30:00',
     't_flume', 'Flume', 219000, 'For Emma, Forever Ago',
     'a_boniver', 'Bon Iver', 3),
    ('p08', '2026-10-21 04:34:00+00', '2026-10-20 21:34:00',
     't_lies', 'Lies', 263000, 'Ones and Sixes',
     'a_low', 'Low', 3),
    ('p09', '2026-10-21 04:39:00+00', '2026-10-20 21:39:00',
     't_masterpiece', 'Masterpiece', 240000, 'Masterpiece',
     'a_bigthief', 'Big Thief', 3),
    ('p10', '2026-10-21 04:43:00+00', '2026-10-20 21:43:00',
     't_motion', 'Motion Sickness', 229000, 'Stranger in the Alps',
     'a_phoebe', 'Phoebe Bridgers', 3);

insert into marts.fct_listening_sessions values
    (1, '2026-10-19 04:00:00+00', '2026-10-19 04:17:23+00', 3, 16.67, 2),
    (2, '2026-10-19 15:00:00+00', '2026-10-19 15:17:00+00', 3, 16.78, 3),
    (3, '2026-10-21 04:30:00+00', '2026-10-21 04:46:49+00', 4, 15.85, 4);

insert into marts.mart_daily_listening values
    ('2026-10-18', 3, 16.67, 2),
    ('2026-10-19', 3, 16.78, 3),
    ('2026-10-20', 4, 15.85, 4);

insert into marts.mart_hour_of_week values
    (7, 21, 3, 16.67),
    (1, 8, 3, 16.78),
    (2, 21, 4, 15.85);

insert into marts.mart_artist_streaks values
    ('a_boniver', 'Bon Iver', '2026-10-18', '2026-10-20', 3),
    ('a_low', 'Low', '2026-10-18', '2026-10-20', 3),
    ('a_bigthief', 'Big Thief', '2026-10-19', '2026-10-20', 2),
    ('a_phoebe', 'Phoebe Bridgers', '2026-10-20', '2026-10-20', 1);
