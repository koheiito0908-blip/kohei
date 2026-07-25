(() => {
  "use strict";

  const datePicker = document.getElementById("date-picker");
  const raceList = document.getElementById("race-list");
  const statusBanner = document.getElementById("status-banner");
  const courseStatsEl = document.getElementById("course-stats");
  const statsUpdatedEl = document.getElementById("stats-updated");
  const dataRangeEl = document.getElementById("data-range");
  const template = document.getElementById("race-card-template");

  const todayJst = () => {
    const now = new Date();
    const jst = new Date(now.toLocaleString("en-US", { timeZone: "Asia/Tokyo" }));
    const pad = (n) => String(n).padStart(2, "0");
    return `${jst.getFullYear()}-${pad(jst.getMonth() + 1)}-${pad(jst.getDate())}`;
  };

  function initTabs() {
    document.querySelectorAll(".tab").forEach((btn) => {
      btn.addEventListener("click", () => {
        document.querySelectorAll(".tab").forEach((b) => {
          b.classList.remove("active");
          b.setAttribute("aria-selected", "false");
        });
        btn.classList.add("active");
        btn.setAttribute("aria-selected", "true");
        document.querySelectorAll(".panel").forEach((p) => p.classList.remove("active"));
        document.getElementById(`panel-${btn.dataset.tab}`).classList.add("active");
      });
    });
  }

  async function fetchJson(path) {
    const res = await fetch(path, { cache: "no-store" });
    if (!res.ok) return null;
    return res.json();
  }

  function confidenceClass(label) {
    if (label === "高") return "high";
    if (label === "中") return "mid";
    return "low";
  }

  function fmt(n, digits = 2) {
    return n === null || n === undefined ? "-" : Number(n).toFixed(digits);
  }

  function renderRaces(data) {
    raceList.innerHTML = "";
    statusBanner.hidden = true;

    if (!data) {
      raceList.innerHTML = `<div class="empty-state">この日の平和島データはまだありません。<br>データ収集ワークフローの実行後に表示されます。</div>`;
      return;
    }

    if (data.status === "no_racing") {
      raceList.innerHTML = `<div class="empty-state">この日、平和島は開催されていません。</div>`;
      return;
    }

    if (data.status !== "final") {
      statusBanner.hidden = false;
      statusBanner.textContent = "本日のレースはまだ全て終了していません。展示情報の反映により随時スコアが更新されます。";
    }

    for (const race of data.races) {
      const node = template.content.cloneNode(true);
      const card = node.querySelector(".race-card");
      node.querySelector(".race-no").textContent = `${race.race_number}R`;
      node.querySelector(".race-title").textContent = race.is_canceled
        ? "中止"
        : (race.title || "");

      const confEl = node.querySelector(".confidence");
      if (race.is_canceled) {
        confEl.textContent = "中止";
      } else if (race.confidence) {
        confEl.textContent = `自信度:${race.confidence}`;
        confEl.classList.add(confidenceClass(race.confidence));
      } else {
        confEl.textContent = "-";
      }

      const tbody = node.querySelector("tbody");
      for (const p of race.predictions) {
        const tr = document.createElement("tr");
        if (p.is_absent) {
          tr.innerHTML = `
            <td>-</td>
            <td><span class="pit-chip pit-${p.pit_number}">${p.pit_number}</span></td>
            <td class="name">欠場</td>
            <td colspan="4">-</td>`;
        } else {
          const rankClass = p.predicted_rank <= 3 ? `r${p.predicted_rank}` : "";
          tr.innerHTML = `
            <td><span class="rank-badge ${rankClass}">${p.predicted_rank ?? "-"}</span></td>
            <td><span class="pit-chip pit-${p.pit_number}">${p.pit_number}</span></td>
            <td class="name">${p.racer_name ?? "-"}</td>
            <td>${p.racer_rank ?? "-"}</td>
            <td colspan="2">スコア ${fmt(p.score, 3)}</td>`;
        }
        tbody.appendChild(tr);
      }

      card.querySelector(".race-card-header").addEventListener("click", () => {
        card.classList.toggle("open");
      });

      raceList.appendChild(node);
    }

    if (raceList.children.length > 0) {
      raceList.children[0].classList.add("open");
    }
  }

  function renderCourseStats(stats) {
    if (!stats || !stats.by_pit) {
      courseStatsEl.innerHTML = `<div class="empty-state">統計データはまだありません。</div>`;
      return;
    }
    statsUpdatedEl.textContent = stats.date_range
      ? `集計期間: ${stats.date_range.from} 〜 ${stats.date_range.to}（${stats.total_races_analyzed}レース）`
      : "";
    if (dataRangeEl) {
      dataRangeEl.textContent = stats.date_range
        ? `${stats.date_range.from} 〜 ${stats.date_range.to}`
        : "-";
    }

    courseStatsEl.innerHTML = "";
    for (let pit = 1; pit <= 6; pit++) {
      const s = stats.by_pit[String(pit)] || {};
      const pct = s.win_rate === null || s.win_rate === undefined ? 0 : s.win_rate * 100;
      const row = document.createElement("div");
      row.className = "course-row";
      row.innerHTML = `
        <span class="pit-chip pit-${pit}">${pit}</span>
        <div class="bar-wrap"><div class="bar" style="width:${pct}%"></div></div>
        <span class="pct">${s.win_rate === null || s.win_rate === undefined ? "-" : pct.toFixed(1) + "%"}</span>
      `;
      courseStatsEl.appendChild(row);
    }
  }

  async function loadForDate(dateStr) {
    const [predictions, stats] = await Promise.all([
      fetchJson(`data/predictions/${dateStr}.json`),
      fetchJson("data/stats/course_stats.json"),
    ]);
    renderRaces(predictions);
    renderCourseStats(stats);
  }

  function init() {
    initTabs();
    const initial = todayJst();
    datePicker.value = initial;
    datePicker.max = initial;
    datePicker.addEventListener("change", () => loadForDate(datePicker.value));
    loadForDate(initial);
  }

  init();
})();
