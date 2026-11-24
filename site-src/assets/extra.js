/* 嵌入式能力地图：筛选、掌握度打卡（localStorage）、阅读进度条 */
(function () {
  "use strict";

  var KEY = "embedded-mastery-v1";

  function load() {
    try {
      return JSON.parse(localStorage.getItem(KEY) || "{}") || {};
    } catch (e) {
      return {};
    }
  }

  function save(data) {
    try {
      localStorage.setItem(KEY, JSON.stringify(data));
    } catch (e) {
      /* 隐私模式或配额满：静默失败 */
    }
  }

  var mastery = load();

  function paintLevels() {
    var boxes = document.querySelectorAll(".levels");
    if (!boxes.length) return;
    boxes.forEach(function (box) {
      var p = box.getAttribute("data-point");
      var lv = mastery[p] || 0;
      box.querySelectorAll(".lvl").forEach(function (b) {
        b.classList.toggle("on", Number(b.getAttribute("data-l")) <= lv);
      });
    });
    paintChapters();
  }

  function paintChapters() {
    document.querySelectorAll(".map-chapter").forEach(function (sec) {
      var boxes = sec.querySelectorAll(".levels[data-point]");
      if (!boxes.length) return;
      var sum = 0;
      boxes.forEach(function (b) {
        sum += mastery[b.getAttribute("data-point")] || 0;
      });
      var pct = Math.round((sum / (boxes.length * 3)) * 100);
      var label = sec.querySelector(".local-pct");
      if (label) label.textContent = pct + "%";
    });
  }

  function bindLevels() {
    document.addEventListener("click", function (e) {
      var btn = e.target.closest(".lvl");
      if (!btn) return;
      var box = btn.closest(".levels");
      var p = box.getAttribute("data-point");
      var lv = Number(btn.getAttribute("data-l"));
      var cur = mastery[p] || 0;
      mastery[p] = cur === lv ? lv - 1 : lv;
      if (mastery[p] <= 0) delete mastery[p];
      save(mastery);
      paintLevels();
    });
  }

  function bindFilter() {
    var input = document.getElementById("map-filter");
    if (!input) return;
    var count = document.getElementById("map-count");
    var total = document.querySelectorAll(".map-table tbody tr[data-point]").length;

    function apply() {
      var q = input.value.trim().toLowerCase();
      var shown = 0;
      document.querySelectorAll(".map-chapter").forEach(function (sec) {
        var visible = 0;
        sec.querySelectorAll("tr[data-point]").forEach(function (row) {
          var hit = !q || (row.getAttribute("data-text") || "").indexOf(q) !== -1;
          row.style.display = hit ? "" : "none";
          if (hit) visible++;
        });
        sec.querySelectorAll("tr.sec-row").forEach(function (row) {
          row.style.display = visible ? "" : "none";
        });
        sec.style.display = visible ? "" : "none";
        shown += visible;
      });
      if (count) count.textContent = (q ? shown : total) + " 个技能点";
    }

    input.addEventListener("input", apply);
  }

  function bindReset() {
    var btn = document.getElementById("progress-reset");
    if (!btn) return;
    btn.addEventListener("click", function () {
      if (!window.confirm("清空本机记录的所有掌握度？此操作不可撤销。")) return;
      mastery = {};
      save(mastery);
      paintLevels();
    });
  }

  function scrollBar() {
    var el = document.createElement("div");
    el.className = "scroll-progress";
    document.body.appendChild(el);
    var raf = false;
    function update() {
      var doc = document.documentElement;
      var max = doc.scrollHeight - doc.clientHeight;
      el.style.width = max > 0 ? (doc.scrollTop / max) * 100 + "%" : "0";
      raf = false;
    }
    window.addEventListener("scroll", function () {
      if (!raf) {
        raf = true;
        window.requestAnimationFrame(update);
      }
    }, { passive: true });
    update();
  }

  function init() {
    bindLevels();
    paintLevels();
    bindFilter();
    bindReset();
    scrollBar();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
