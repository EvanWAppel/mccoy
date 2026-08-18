# Loom walkthrough — guide for mccoy

A companion to [RECRUITER-PRIMER.md](RECRUITER-PRIMER.md) task 4: recording a
60–90s onboarding walkthrough of the live no-login demo.

## What Loom is

Loom is a free screen-recording tool (browser extension + desktop app) that
captures your screen, your voice, and optionally a small webcam bubble of your
face in the corner, then instantly gives you a **shareable link** — no file to
host yourself. You hit record, walk through something on screen while talking,
hit stop, and Loom hands you a URL that plays in any browser.

Why Loom specifically for this project: for the forward-deployed and DevRel
roles being targeted, *recording yourself demoing a product to a stranger* is
literally the job skill — so the Loom doubles as a work sample of that skill.

Alternatives (QuickTime, macOS Cmd-Shift-5, CleanShot) produce a file you then
have to host somewhere. Loom's whole value is the instant hosted link. For this
use case, use Loom.

## How you'll use it for mccoy

The frame: *pretend a recruiter just landed on the demo and you're showing them
around* — the "onboard a stranger into a data app" gesture Hex and the
forward-deployed roles are evaluating. Target: **60–90 seconds** on the **live
no-login demo** at mccoy.evanappel.me.

### Setup (one-time)

1. Sign up at loom.com (free tier is plenty).
2. Install the Chrome extension (or desktop app). Grant screen + mic
   permission.
3. Optional: turn the webcam bubble on — a face in the corner reads warmer,
   but it's your call. **Mic audio is the non-negotiable part.**

### The recording (~90s)

Follow the primer's script:

1. Land on **mccoy.evanappel.me logged out** — one line on what it is
   ("a live Spotify listening dashboard in Python on Dash, and this is the
   no-login demo").
2. Show **Stats** — the artist grid, genre chart.
3. Show **Trends** — one sentence on the weekly Railway cron snapshotting into
   Postgres so you get trend history.
4. One **Rustle** gesture — the crate-digging playlist sandbox.
5. Optionally the **Network** graph.
6. Close on the architecture in ~10 words ("all Python, one language, 342
   tests, CI, live on Railway").

### Two hard rules

- **Do not log in on camera.** Stay on the demo path — keeps your private
  listening data off the recording *and* proves the no-login demo actually
  works, which is the whole recruiter pitch.
- **Keep it under 90 seconds.** Script it, maybe do two takes. Recruiters
  won't watch a rambling three-minute one.

### After recording

- Loom gives you a share link — set it to **"anyone with the link"** (unlisted,
  no login wall, or a recruiter can't watch it).
- The link goes two places: the top of the **README** and the **About tab**
  (`components/about.py`, near the existing `LINKEDIN_URL` / `REPO_URL` /
  `RESUME_URL` constants).

Wiring the link into the README and About tab (with a matching test update) is
something the coding agent can do once you have the URL — just hand it over.

## Suggested order

Capture the screenshots (primer task 3) **before** recording, so you're walking
through a demo you've already confirmed renders cleanly on every tab — no
cold-start surprise live on the recording.
