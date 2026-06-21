/* Rustling gesture input (Group W).
 *
 * Pointer Events (touch + mouse drag) and keyboard arrows resolve to
 * a single gesture {direction, ts} written into the rustle-gesture
 * dcc.Store via dash_clientside.set_props. Listeners live on
 * document because Dash re-renders the card area on every update.
 */
/* Group X: clientside audio for the free preview_url path. */
(function () {
  var FADE_MS = 200; // X-03
  var FADE_STEPS = 10;
  // Short silent wav so the unlock tap has something to play
  var SILENT_WAV =
    "data:audio/wav;base64,UklGRiQAAABXQVZFZm10IBAAAAABAAEAQB8AAEAf" +
    "AAABAAgAZGF0YQAAAAA=";

  function getAudio() {
    return document.getElementById("rustle-audio");
  }

  function fadeOut(audio, done) {
    if (!audio || audio.paused) {
      if (done) done();
      return;
    }
    var step = audio.volume / FADE_STEPS;
    var timer = setInterval(function () {
      var v = audio.volume - step;
      if (v <= 0) {
        audio.volume = 0;
        audio.pause();
        clearInterval(timer);
        if (done) done();
      } else {
        audio.volume = v;
      }
    }, FADE_MS / FADE_STEPS);
  }

  window.dash_clientside = window.dash_clientside || {};
  window.dash_clientside.rustle = {
    // X-02..X-04: on card change, fade the old preview out, then
    // play the new card's preview (or stay silent without one)
    playPreview: function (idx, queue, view, unlocked) {
      var audio = getAudio();
      if (!audio) return window.dash_clientside.no_update;
      // Y: premium plays full tracks via the Web Playback SDK; keep
      // the free preview silent so they don't double up.
      if (window.__rustlePremiumActive) {
        if (!audio.paused) audio.pause();
        return window.dash_clientside.no_update;
      }
      var track =
        view === "track" && unlocked && queue && queue[idx]
          ? queue[idx]
          : null;
      fadeOut(audio, function () {
        if (!track || !track.preview_url) return; // X-04
        audio.src = track.preview_url;
        audio.volume = 1;
        audio.play().catch(function () {
          /* autoplay rejection — user can gesture again */
        });
      });
      return window.dash_clientside.no_update;
    },

    // X-05: prime the audio element inside the tap gesture
    unlockAudio: function (n_clicks) {
      if (!n_clicks) return window.dash_clientside.no_update;
      var audio = getAudio();
      if (audio) {
        audio.src = SILENT_WAV;
        audio.play().catch(function () {});
      }
      return true;
    },
  };
})();

(function () {
  var COMMIT_PX = 80; // W-02: minimum drag distance to commit
  var TAP_PX = 10; // AA-01: max movement that still counts as a tap

  var drag = null; // {x, y, onArt} of pointerdown

  function cardArea(target) {
    return (
      target &&
      target.closest &&
      target.closest('[data-rustle-card-area="true"]')
    );
  }

  // AA-01: did the gesture start on a track card's album art?
  function onArt(target) {
    return (
      target &&
      target.closest &&
      target.closest('[data-rustle-art="true"]')
    );
  }

  function topCard() {
    var slot = document.querySelector(".rustle-stack__card--0");
    return slot ? slot.firstElementChild : null;
  }

  // W-03: hand the resolved gesture to Dash
  function sendGesture(direction) {
    if (window.dash_clientside && window.dash_clientside.set_props) {
      window.dash_clientside.set_props("rustle-gesture", {
        data: { direction: direction, ts: Date.now() },
      });
    }
  }

  function animateExit(card, direction) {
    // V-03: optimistic exit while the server round-trip runs
    card.classList.add(
      "rustle-card--exiting",
      "rustle-card--exiting-" + direction
    );
  }

  function commit(direction) {
    var card = topCard();
    if (!card) {
      sendGesture(direction);
      return;
    }
    var isTrack = card.classList.contains("rustle-card--track");
    if (direction === "up" && isTrack) {
      if (card.querySelector(".rustle-card__badge")) {
        // Z-03: already in the target — shake, don't dispatch
        card.classList.add("rustle-card--shake");
        setTimeout(function () {
          card.classList.remove("rustle-card--shake");
        }, 250);
        return;
      }
      // Z-05: stamp first, then fly the card off and dispatch
      var stamp = document.createElement("div");
      stamp.className = "added-stamp";
      stamp.textContent = "Added";
      card.appendChild(stamp);
      setTimeout(function () {
        animateExit(card, "up");
        sendGesture("up");
      }, 400);
      return;
    }
    animateExit(card, direction);
    sendGesture(direction);
  }

  // W-01 / W-05: one Pointer Events path for touch and mouse drag
  document.addEventListener("pointerdown", function (ev) {
    if (!cardArea(ev.target)) return;
    drag = { x: ev.clientX, y: ev.clientY, onArt: !!onArt(ev.target) };
  });

  document.addEventListener("pointermove", function (ev) {
    if (!drag) return;
    var card = topCard();
    if (!card) return;
    var dx = ev.clientX - drag.x;
    var dy = ev.clientY - drag.y;
    card.style.transform =
      "translate(" + dx + "px, " + dy + "px) " +
      "rotate(" + dx / 20 + "deg)";
  });

  document.addEventListener("pointerup", function (ev) {
    if (!drag) return;
    var dx = ev.clientX - drag.x;
    var dy = ev.clientY - drag.y;
    var startedOnArt = drag.onArt;
    drag = null;
    var ax = Math.abs(dx);
    var ay = Math.abs(dy);
    var card = topCard();
    // AA-01: a near-stationary tap on a track card's album art
    // drills into that track's album (level 2 → level 3 only).
    if (
      Math.max(ax, ay) < TAP_PX &&
      startedOnArt &&
      card &&
      card.classList.contains("rustle-card--track")
    ) {
      card.style.transform = "";
      sendGesture("tap-art");
      return;
    }
    if (Math.max(ax, ay) < COMMIT_PX) {
      if (card) card.style.transform = "";
      return;
    }
    // W-02: dominant axis wins
    var direction;
    if (ax >= ay) {
      direction = dx < 0 ? "left" : "right";
    } else {
      direction = dy < 0 ? "up" : "down";
    }
    commit(direction);
  });

  document.addEventListener("pointercancel", function () {
    drag = null;
    var card = topCard();
    if (card) card.style.transform = "";
  });

  // Native image drag would swallow mouse swipes on desktop
  document.addEventListener("dragstart", function (ev) {
    if (cardArea(ev.target)) ev.preventDefault();
  });

  // W-04: keyboard bindings (Enter doubles as Up = commit)
  document.addEventListener("keydown", function (ev) {
    var active = document.activeElement;
    var tag = active ? active.tagName : "";
    if (tag === "INPUT" || tag === "TEXTAREA") return;
    if (!document.querySelector('[data-rustle-card-area="true"]')) {
      return;
    }
    var map = {
      ArrowLeft: "left",
      ArrowRight: "right",
      ArrowUp: "up",
      ArrowDown: "down",
      Enter: "up",
    };
    var direction = map[ev.key];
    if (!direction) return;
    ev.preventDefault();
    commit(direction);
  });
})();

/* ===================================================================
 * Group Y — Audio: Premium Web Playback SDK
 * Self-contained block. Coordinates with the Group X playPreview path
 * via window.__rustlePremiumActive (playPreview early-returns when set).
 * =================================================================== */
(function () {
  "use strict";

  var SDK_SRC = "https://sdk.scdn.co/spotify-player.js";
  var SDK_SCRIPT_ID = "spotify-web-playback-sdk"; // dedupe marker
  var READY_TIMEOUT_MS = 5000; // Y-05
  var player = null;
  var initStarted = false;

  // Flag the Group X playPreview clientside fn reads to suppress the
  // free preview while premium plays full tracks.
  window.__rustlePremiumActive = window.__rustlePremiumActive || false;

  function setProps(id, props) {
    if (window.dash_clientside && window.dash_clientside.set_props) {
      window.dash_clientside.set_props(id, props);
    }
  }

  window.dash_clientside = window.dash_clientside || {};
  window.dash_clientside.rustle = window.dash_clientside.rustle || {};

  // Y-02: inject the SDK <script> tag exactly once, only for premium.
  // Side-effect-only clientside callback → always returns a concrete
  // string (never dash_clientside.no_update) to the sink store.
  window.dash_clientside.rustle.injectSDK = function (product) {
    if (product !== "premium") {
      return "not-premium";
    }
    if (document.getElementById(SDK_SCRIPT_ID)) {
      return "already-present";
    }
    var tag = document.createElement("script");
    tag.id = SDK_SCRIPT_ID;
    tag.src = SDK_SRC;
    tag.async = true;
    document.head.appendChild(tag);
    return "injected";
  };

  // Y-03: build and connect the player once the SDK script is ready.
  function initPlayer() {
    if (initStarted || typeof Spotify === "undefined") {
      return;
    }
    initStarted = true;

    player = new Spotify.Player({
      name: "mccoy Rustle",
      // Y-03: the SDK asks for a fresh token; fetch it from /token.
      getOAuthToken: function (cb) {
        fetch("/token", { credentials: "same-origin" })
          .then(function (r) {
            return r.ok ? r.json() : null;
          })
          .then(function (d) {
            if (d && d.access_token) {
              cb(d.access_token);
            }
          })
          .catch(function (e) {
            console.warn("Rustle: /token fetch failed", e);
          });
      },
      volume: 1.0,
    });

    // Y-03: capture the device id so the server can target playback.
    player.addListener("ready", function (data) {
      window.__rustlePremiumActive = true;
      console.info("Rustle: premium device ready", data.device_id);
      setProps("rustle-device-id", { data: data.device_id });
    });

    player.addListener("not_ready", function (data) {
      // Device went offline; drop back to the free path.
      window.__rustlePremiumActive = false;
      console.warn("Rustle: premium device offline", data.device_id);
    });

    // Y-05: any error leaves device-id empty → free-preview fallback.
    var onErr = function (label) {
      return function (e) {
        console.warn("Rustle: SDK " + label, e && e.message);
      };
    };
    player.addListener("initialization_error", onErr("init error"));
    player.addListener("authentication_error", onErr("auth error"));
    player.addListener("account_error", onErr("account error"));
    player.addListener("playback_error", onErr("playback error"));

    player.connect();

    // Y-05: if "ready" never fires within ~5s, log and stay on the
    // free preview path (rustle-device-id is never written).
    setTimeout(function () {
      if (!window.__rustlePremiumActive) {
        console.warn(
          "Rustle: Web Playback SDK not ready within " +
            READY_TIMEOUT_MS +
            "ms; using free preview fallback"
        );
      }
    }, READY_TIMEOUT_MS);
  }

  // Y-03: the SDK invokes this global as soon as its script loads.
  // Chain any pre-existing handler so we don't clobber it.
  var prevReady = window.onSpotifyWebPlaybackSDKReady;
  window.onSpotifyWebPlaybackSDKReady = function () {
    if (typeof prevReady === "function") {
      prevReady();
    }
    initPlayer();
  };
})();
