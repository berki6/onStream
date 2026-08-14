/* OnStream demo player helpers — quality, keyboard, DVR-safe storyboard. */
(function (global) {
  const cueArrow = "--" + ">";

  function seekableEnd(video) {
    const d = video.duration;
    if (Number.isFinite(d) && d > 0) return d;
    try {
      if (video.seekable && video.seekable.length) {
        return video.seekable.end(video.seekable.length - 1);
      }
    } catch (_) { /* ignore */ }
    return 0;
  }

  function parseSbVtt(text) {
    const cues = [];
    const blocks = text.replace(/\r/g, "").split("\n\n");
    const ts = new RegExp(
      "(\\d{2}):(\\d{2}):(\\d{2})\\.(\\d{3})\\s+" +
        cueArrow +
        "\\s+(\\d{2}):(\\d{2}):(\\d{2})\\.(\\d{3})"
    );
    const xywh = /#xywh=(\d+),(\d+),(\d+),(\d+)/;
    const toSec = (h, m, s, ms) => (+h) * 3600 + (+m) * 60 + (+s) + (+ms) / 1000;
    for (const block of blocks) {
      const lines = block.split("\n").filter(Boolean);
      const timeLine = lines.find((l) => l.includes(cueArrow));
      const uriLine = lines.find((l) => l.includes("#xywh="));
      if (!timeLine || !uriLine) continue;
      const tm = timeLine.match(ts);
      const xy = uriLine.match(xywh);
      if (!tm || !xy) continue;
      cues.push({
        start: toSec(tm[1], tm[2], tm[3], tm[4]),
        end: toSec(tm[5], tm[6], tm[7], tm[8]),
        x: +xy[1],
        y: +xy[2],
        w: +xy[3],
        h: +xy[4],
      });
    }
    return cues;
  }

  function storyboardFromMaster(src) {
    try {
      const u = new URL(src, location.origin);
      if (!/master\.m3u8$/.test(u.pathname) || /\/live\//.test(u.pathname)) {
        return null;
      }
      u.pathname = u.pathname.replace(/master\.m3u8$/, "storyboard.vtt");
      const img = new URL(u.href);
      img.pathname = img.pathname.replace(/storyboard\.vtt$/, "storyboard.jpg");
      return { vtt: u.href, img: img.href };
    } catch {
      return null;
    }
  }

  function wireStoryboard(video, vttUrl, imgUrl, statusEl) {
    const box = document.getElementById("sbPreview") || document.getElementById("thumb");
    if (!box || !vttUrl || !imgUrl) {
      if (statusEl) {
        statusEl.textContent =
          "No scrub preview — sprite is written at VOD transcode or after live archive promote.";
      }
      return;
    }
    const img = box.querySelector("img") || document.getElementById("sbImg");
    if (!img) return;
    fetch(vttUrl)
      .then((r) => (r.ok ? r.text() : Promise.reject()))
      .then((text) => {
        const cues = parseSbVtt(text);
        if (!cues.length) throw new Error("empty");
        img.src = imgUrl;
        if (statusEl) statusEl.textContent = "Hover the player for scrub previews.";
        video.onmousemove = (ev) => {
          const rect = video.getBoundingClientRect();
          const x = ev.clientX - rect.left;
          const ratio = Math.max(0, Math.min(1, x / rect.width));
          const end = seekableEnd(video) || cues[cues.length - 1].end;
          const t = ratio * end;
          const cue =
            cues.find((c) => t >= c.start && t < c.end) ||
            cues[Math.min(cues.length - 1, Math.floor(ratio * cues.length))];
          if (!cue) return;
          box.style.display = "block";
          box.style.position = "fixed";
          box.style.left = Math.max(8, ev.clientX - 80) + "px";
          box.style.top = Math.max(8, rect.top - 100) + "px";
          img.style.left = -cue.x + "px";
          img.style.top = -cue.y + "px";
        };
        video.onmouseleave = () => {
          box.style.display = "none";
        };
      })
      .catch(() => {
        if (statusEl) {
          statusEl.textContent =
            "No scrub preview — sprite is written at VOD transcode or after live archive promote.";
        }
      });
  }

  function wireQuality(hls, selectEl) {
    if (!hls || !selectEl) return;
    const fill = () => {
      const levels = hls.levels || [];
      selectEl.innerHTML = "";
      const auto = document.createElement("option");
      auto.value = "-1";
      auto.textContent = "Auto";
      selectEl.appendChild(auto);
      levels.forEach((lv, i) => {
        const opt = document.createElement("option");
        opt.value = String(i);
        const h = lv.height || 0;
        opt.textContent = h ? h + "p" : "Level " + (i + 1);
        selectEl.appendChild(opt);
      });
      selectEl.disabled = levels.length < 2;
      selectEl.value = String(hls.currentLevel);
      if (selectEl.value === "") selectEl.value = "-1";
    };
    hls.on(Hls.Events.MANIFEST_PARSED, fill);
    hls.on(Hls.Events.LEVELS_UPDATED, fill);
    selectEl.onchange = () => {
      hls.currentLevel = Number(selectEl.value);
    };
  }

  function wireKeyboard(video) {
    const handler = (ev) => {
      const tag = (ev.target && ev.target.tagName) || "";
      if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT") return;
      const key = ev.key;
      const end = seekableEnd(video);
      if (key === " " || key === "k" || key === "K") {
        ev.preventDefault();
        if (video.paused) video.play();
        else video.pause();
      } else if (key === "j" || key === "J" || key === "ArrowLeft") {
        ev.preventDefault();
        video.currentTime = Math.max(0, (video.currentTime || 0) - 10);
      } else if (key === "l" || key === "L" || key === "ArrowRight") {
        ev.preventDefault();
        video.currentTime = Math.min(end || 1e9, (video.currentTime || 0) + 10);
      } else if (key === "f" || key === "F") {
        if (document.fullscreenElement) document.exitFullscreen();
        else video.requestFullscreen && video.requestFullscreen();
      } else if (key === "m" || key === "M") {
        video.muted = !video.muted;
      } else if (key >= "0" && key <= "9" && end > 0) {
        video.currentTime = end * (Number(key) / 10);
      }
    };
    document.addEventListener("keydown", handler);
    return () => document.removeEventListener("keydown", handler);
  }

  function attachHls(video, src, opts) {
    opts = opts || {};
    if (!global.Hls || !Hls.isSupported()) return null;
    const hls = new Hls({
      enableWorker: true,
      renderTextTracksNatively: true,
      backBufferLength: /\/ll\//.test(src) ? 30 : Infinity,
      liveSyncDurationCount: /\/ll\//.test(src) ? 2 : 3,
      lowLatencyMode: /\/ll\//.test(src),
    });
    if (opts.qualitySelect) wireQuality(hls, opts.qualitySelect);
    if (typeof opts.onHls === "function") opts.onHls(hls);
    hls.attachMedia(video);
    hls.loadSource(src);
    return hls;
  }

  global.OnStreamDemo = {
    seekableEnd,
    parseSbVtt,
    storyboardFromMaster,
    wireStoryboard,
    wireQuality,
    wireKeyboard,
    attachHls,
  };
})(window);
