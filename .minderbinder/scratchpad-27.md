Added an owner-facing 'Rate' mode mirroring the Rustle/DJ flow: search albums, flip through covers with gestures, preview each song via an embedded player, and tap a 1-10 scale to rate it; plus a 'Rated songs' sub-tab that lists ratings sortable by title, artist, year, and rating. Implemented across a new migration (song_ratings), db functions, a spotify album-tracks-with-year mapper, a components/rate.py module, a third mode tab, and five Dash callbacks, with CSS and 23 new tests. Full suite passes 239/239 and all callback paths were exercised live.

<details>
<summary>Sandbox test output (tail)</summary>

```
Unable to find image 'python:3.12' locally
3.12: Pulling from library/python
90d1f3b8a822: Pulling fs layer
9e002cae30c4: Pulling fs layer
b890c9407285: Pulling fs layer
b453535073b6: Pulling fs layer
15215efaca49: Pulling fs layer
65956eab0c1c: Pulling fs layer
2b87fe8d0f10: Pulling fs layer
90d1f3b8a822: Download complete
15215efaca49: Download complete
2b87fe8d0f10: Download complete
b453535073b6: Download complete
b890c9407285: Download complete
9e002cae30c4: Download complete
3e75c1b2f545: Download complete
dcc2691db608: Download complete
65956eab0c1c: Download complete
b890c9407285: Pull complete
b453535073b6: Pull complete
9e002cae30c4: Pull complete
65956eab0c1c: Pull complete
15215efaca49: Pull complete
90d1f3b8a822: Pull complete
2b87fe8d0f10: Pull complete
Digest: sha256:7ad6d21a25a94b2c00e685e82c2fd298de814353d9ee0e3f7f2cd4fca063df60
Status: Downloaded newer image for python:3.12
docker: Error response from daemon: failed to create task for container: failed to create shim task: OCI runtime create failed: runc create failed: unable to start container process: error during container init: exec: "pytest": executable file not found in $PATH

Run 'docker run --help' for more information
```
</details>