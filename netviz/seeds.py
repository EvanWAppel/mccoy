"""Curated hard-bop seed musicians + crawl bounding constants.

The crawl snowballs outward from these seeds. All limits are plain
constants so the graph can be grown later by raising them (or by
adding a new seed genre) without touching the crawl logic.
"""

# Seed set (Evan). Hard-bop core (2026-08-08) + a modal/post-bop axis
# around McCoy Tyner (2026-08-09): the Coltrane classic quartet and the
# Blue Note / Miles post-bop players, so the graph spans the genres
# closest to the app's namesake pianist.
SEED_MUSICIANS = [
    # Hard-bop core
    "Art Blakey",
    "Horace Silver",
    "Clifford Brown",
    "Lee Morgan",
    "Hank Mobley",
    "Sonny Rollins",
    "Cannonball Adderley",
    "Kenny Dorham",
    "Wayne Shorter",
    "Freddie Hubbard",
    "Joe Henderson",
    "Jimmy Smith",
    "McCoy Tyner",
    # Modal + post-bop axis
    "John Coltrane",
    "Elvin Jones",
    "Jimmy Garrison",
    "Herbie Hancock",
    "Bill Evans",
    "Miles Davis",
    "Ron Carter",
    "Tony Williams",
]

# --- Crawl bounding (see prd.md "Crawl / Ingest Design") ---

# How many musicians the BFS expands (crawls). This bounds crawl TIME
# (each release's personnel is fetched at Discogs' 1 req/sec limit); the
# rendered graph is separately bounded by GRAPH_NODE_LIMIT below, and
# the crawl admits many more sideman nodes than it expands.
NODE_CAP = 150

# How many hops out from the seeds to expand.
MAX_HOPS = 2

# Cap releases fetched per musician so one prolific player (Art Blakey
# appears on hundreds) can't dominate the crawl — and to bound runtime.
PER_MUSICIAN_RELEASE_CAP = 30

# Drop edges weaker than this. The top-degree core is near-complete at
# low thresholds (a hairball), so we keep only pairs who shared this
# many releases — the meaningful, recurring collaborations.
MIN_EDGE_WEIGHT = 6

# Cap the *rendered* graph to the most-connected musicians. The crawl
# admits far more sidemen than make a readable canvas; keeping the top
# nodes by degree yields a dense, navigable core.
GRAPH_NODE_LIMIT = 250

# The co-credit snowball drifts through bebop into the swing/big-band
# world (dense orchestra cliques with huge shared-session counts). Focus
# the rendered graph on McCoy Tyner's era onward so those cliques don't
# crowd out the hard-bop/modal/post-bop core.
GRAPH_MIN_YEAR = 1955
