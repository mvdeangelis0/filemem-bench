/**
 * Beat driver for filemem-bench visuals.
 * Shows exactly one narration line + one mech line per beat (no stacked opacity).
 */
(function () {
  const LOOP_MS = 22000;
  const N = 6;

  function applyBeat(story, beat) {
    story.dataset.beat = String(beat);

    story.querySelectorAll(".narration").forEach(function (box) {
      var lines = box.querySelectorAll(".beat-line");
      lines.forEach(function (el, i) {
        el.classList.toggle("is-on", i === beat);
      });
    });

    story.querySelectorAll(".mech").forEach(function (box) {
      var lines = box.querySelectorAll(".mech-line");
      lines.forEach(function (el, i) {
        el.classList.toggle("is-on", i === beat);
      });
    });

    story.querySelectorAll(".progress span").forEach(function (el, i) {
      el.classList.toggle("is-on", i === beat);
    });

    story.querySelectorAll(".blob.step, .step").forEach(function (el) {
      var on = el.classList.contains("b" + beat);
      el.classList.toggle("is-on", on);
    });
  }

  function tick() {
    var beat = Math.floor((performance.now() % LOOP_MS) / (LOOP_MS / N));
    document.querySelectorAll(".story").forEach(function (story) {
      if (story.dataset.beat !== String(beat)) {
        applyBeat(story, beat);
      }
    });
  }

  function boot() {
    document.querySelectorAll(".story").forEach(function (story) {
      applyBeat(story, 0);
    });
    setInterval(tick, 100);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }
})();
