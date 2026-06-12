/* Rustling gesture input (Group W).
 *
 * Pointer Events (touch + mouse drag) and keyboard arrows resolve to
 * a single gesture {direction, ts} written into the rustle-gesture
 * dcc.Store via dash_clientside.set_props. Listeners live on
 * document because Dash re-renders the card area on every update.
 */
(function () {
  var COMMIT_PX = 80; // W-02: minimum drag distance to commit

  var drag = null; // {x, y} of pointerdown

  function cardArea(target) {
    return (
      target &&
      target.closest &&
      target.closest('[data-rustle-card-area="true"]')
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

  function commit(direction) {
    var card = topCard();
    if (card) {
      // V-03: optimistic exit while the server round-trip runs
      card.classList.add(
        "rustle-card--exiting",
        "rustle-card--exiting-" + direction
      );
    }
    sendGesture(direction);
  }

  // W-01 / W-05: one Pointer Events path for touch and mouse drag
  document.addEventListener("pointerdown", function (ev) {
    if (!cardArea(ev.target)) return;
    drag = { x: ev.clientX, y: ev.clientY };
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
    drag = null;
    var ax = Math.abs(dx);
    var ay = Math.abs(dy);
    var card = topCard();
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
