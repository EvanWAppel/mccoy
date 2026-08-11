"""Curated hard-bop seed musicians + crawl bounding constants.

The crawl snowballs outward from these seeds. All limits are plain
constants so the graph can be grown later by raising them (or by
adding a new seed genre) without touching the crawl logic.
"""

# Confirmed hard-bop seed set (Evan, 2026-08-08). McCoy Tyner added —
# the app's namesake pianist.
SEED_MUSICIANS = [
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
]

# --- Crawl bounding (see prd.md "Crawl / Ingest Design") ---

# Target graph size; the BFS stops admitting new musicians past this.
NODE_CAP = 200

# How many hops out from the seeds to expand.
MAX_HOPS = 2

# Cap releases fetched per musician so one prolific player (Art Blakey
# appears on hundreds) can't dominate the crawl.
PER_MUSICIAN_RELEASE_CAP = 40

# Once over the node budget, drop edges weaker than this (single
# shared release = noise).
MIN_EDGE_WEIGHT = 2
