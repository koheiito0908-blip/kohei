"use strict";

const TIER_SCORE = { S: 4, A: 3, B: 2, C: 1, D: 0 };
const CATEGORIES = ["heroes", "pets", "gear"];
const DATA = { heroes: [], pets: [], gear: [] };
const OWNED_KEY = "sh-owned";
const DRAFTS_KEY = "sh-drafts";

let owned = loadOwned();
let drafts = loadDrafts();

async function loadData() {
  const [heroes, pets, gear] = await Promise.all(
    CATEGORIES.map((c) => fetch(`data/${c}.json`).then((r) => r.json()))
  );
  DATA.heroes = heroes;
  DATA.pets = pets;
  DATA.gear = gear;
}

function loadOwned() {
  try {
    const raw = JSON.parse(localStorage.getItem(OWNED_KEY) || "{}");
    return {
      heroes: new Set(raw.heroes || []),
      pets: new Set(raw.pets || []),
      gear: new Set(raw.gear || []),
    };
  } catch {
    return { heroes: new Set(), pets: new Set(), gear: new Set() };
  }
}

function saveOwned() {
  localStorage.setItem(
    OWNED_KEY,
    JSON.stringify({
      heroes: [...owned.heroes],
      pets: [...owned.pets],
      gear: [...owned.gear],
    })
  );
}

function loadDrafts() {
  try {
    return JSON.parse(localStorage.getItem(DRAFTS_KEY) || "[]");
  } catch {
    return [];
  }
}

function saveDrafts() {
  localStorage.setItem(DRAFTS_KEY, JSON.stringify(drafts));
}

/* ---------- タブ切り替え ---------- */
function setupTabs() {
  document.querySelectorAll(".tab-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      document.querySelectorAll(".tab-btn").forEach((b) => b.classList.remove("active"));
      document.querySelectorAll(".tab-panel").forEach((p) => p.classList.remove("active"));
      btn.classList.add("active");
      document.getElementById(`tab-${btn.dataset.tab}`).classList.add("active");
    });
  });
}

/* ---------- 一覧・検索 ---------- */
function renderBrowse() {
  const category = document.getElementById("browse-category").value;
  const search = document.getElementById("browse-search").value.trim().toLowerCase();
  const tier = document.getElementById("browse-tier").value;
  const list = DATA[category].filter((item) => {
    const matchesSearch = !search || item.name.toLowerCase().includes(search);
    const matchesTier = !tier || item.tier === tier;
    return matchesSearch && matchesTier;
  });
  const container = document.getElementById("browse-list");
  container.innerHTML = "";
  if (list.length === 0) {
    container.innerHTML = `<p class="empty">該当データがありません。</p>`;
    return;
  }
  for (const item of list) {
    container.appendChild(renderCard(item));
  }
}

function renderCard(item) {
  const el = document.createElement("div");
  el.className = "card";
  const sub = item.role || item.effect_type || item.slot || "";
  const tags = (item.synergy_tags || item.recommended_for || [])
    .map((t) => `<span class="tag">${escapeHtml(t)}</span>`)
    .join("");
  const source = item.source
    ? `${escapeHtml(item.source.type || "")} / ${escapeHtml(item.source.detail || "")} / ${escapeHtml(
        item.source.date || ""
      )}`
    : "";
  el.innerHTML = `
    <div class="card-head">
      <span class="tier tier-${escapeHtml(item.tier || "")}">${escapeHtml(item.tier || "-")}</span>
      <strong>${escapeHtml(item.name)}</strong>
    </div>
    <div class="card-sub">${escapeHtml(item.rarity || "")} ${escapeHtml(sub)}</div>
    <div class="card-tags">${tags}</div>
    <p class="card-notes">${escapeHtml(item.notes || item.effect || "")}</p>
    <p class="card-source">出典: ${source || "不明"} / 信頼度: ${escapeHtml(item.confidence || "不明")}</p>
  `;
  return el;
}

function escapeHtml(s) {
  return String(s ?? "").replace(/[&<>"']/g, (c) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#39;",
  })[c]);
}

/* ---------- 編成シミュレーター ---------- */
function renderOwnedCheckboxes() {
  renderOwnedList("heroes", "owned-heroes");
  renderOwnedList("pets", "owned-pets");
  renderOwnedList("gear", "owned-gear");
}

function renderOwnedList(category, containerId) {
  const container = document.getElementById(containerId);
  container.innerHTML = "";
  for (const item of DATA[category]) {
    const id = `${category}-${item.id}`;
    const label = document.createElement("label");
    label.className = "owned-item";
    label.innerHTML = `
      <input type="checkbox" id="${id}" ${owned[category].has(item.id) ? "checked" : ""}>
      <span class="tier tier-${escapeHtml(item.tier || "")}">${escapeHtml(item.tier || "-")}</span>
      ${escapeHtml(item.name)}
    `;
    label.querySelector("input").addEventListener("change", (e) => {
      if (e.target.checked) owned[category].add(item.id);
      else owned[category].delete(item.id);
      saveOwned();
    });
    container.appendChild(label);
  }
}

function combinations(arr, k) {
  const results = [];
  function helper(start, combo) {
    if (combo.length === k) {
      results.push([...combo]);
      return;
    }
    for (let i = start; i < arr.length; i++) {
      combo.push(arr[i]);
      helper(i + 1, combo);
      combo.pop();
    }
  }
  helper(0, []);
  return results;
}

function scoreTeam(team) {
  const tierSum = team.reduce((s, h) => s + (TIER_SCORE[h.tier] ?? 0), 0);
  const roles = new Set(team.map((h) => h.role).filter(Boolean));
  const roleBonus = roles.size * 1.5;
  let synergyBonus = 0;
  for (let i = 0; i < team.length; i++) {
    for (let j = i + 1; j < team.length; j++) {
      const a = new Set(team[i].synergy_tags || []);
      const shared = (team[j].synergy_tags || []).filter((t) => a.has(t));
      synergyBonus += shared.length * 0.5;
    }
  }
  return { total: tierSum + roleBonus + synergyBonus, tierSum, roleBonus, synergyBonus };
}

function bestTeam(ownedHeroes, teamSize) {
  if (ownedHeroes.length <= teamSize) {
    return [{ team: ownedHeroes, score: scoreTeam(ownedHeroes) }];
  }
  // 総当たりだと組み合わせ爆発するので、目安として15C(teamSize)未満なら全探索、
  // それ以上は貪欲法 + ローカル探索(swap)で近似する。
  const combosCount = binomial(ownedHeroes.length, teamSize);
  let candidates = [];
  if (combosCount <= 20000) {
    for (const combo of combinations(ownedHeroes, teamSize)) {
      candidates.push({ team: combo, score: scoreTeam(combo) });
    }
  } else {
    const sorted = [...ownedHeroes].sort((a, b) => (TIER_SCORE[b.tier] ?? 0) - (TIER_SCORE[a.tier] ?? 0));
    let team = sorted.slice(0, teamSize);
    let bench = sorted.slice(teamSize);
    let improved = true;
    let iterations = 0;
    while (improved && iterations < 200) {
      improved = false;
      iterations++;
      for (let ti = 0; ti < team.length; ti++) {
        for (let bi = 0; bi < bench.length; bi++) {
          const trial = [...team];
          trial[ti] = bench[bi];
          if (scoreTeam(trial).total > scoreTeam(team).total) {
            const removed = team[ti];
            team = trial;
            bench[bi] = removed;
            improved = true;
          }
        }
      }
    }
    candidates.push({ team, score: scoreTeam(team) });
  }
  candidates.sort((a, b) => b.score.total - a.score.total);
  // 同一メンバー構成の重複を除いて上位3件
  const seen = new Set();
  const top = [];
  for (const c of candidates) {
    const key = c.team.map((h) => h.id).sort().join(",");
    if (seen.has(key)) continue;
    seen.add(key);
    top.push(c);
    if (top.length >= 3) break;
  }
  return top;
}

function binomial(n, k) {
  if (k > n) return 0;
  let res = 1;
  for (let i = 0; i < k; i++) res = (res * (n - i)) / (i + 1);
  return Math.round(res);
}

function bestPet(ownedPets, teamTags) {
  if (ownedPets.length === 0) return null;
  const scored = ownedPets.map((p) => {
    const overlap = (p.synergy_tags || []).filter((t) => teamTags.has(t)).length;
    return { pet: p, score: (TIER_SCORE[p.tier] ?? 0) + overlap };
  });
  scored.sort((a, b) => b.score - a.score);
  return scored[0];
}

function assignGear(ownedGear, team) {
  const used = new Set();
  const assignments = [];
  for (const hero of team) {
    const candidates = ownedGear
      .filter((g) => !used.has(g.id))
      .filter((g) => (g.recommended_for || []).includes(hero.id) || (g.recommended_for || []).includes(hero.role))
      .sort((a, b) => (TIER_SCORE[b.tier] ?? 0) - (TIER_SCORE[a.tier] ?? 0));
    if (candidates.length > 0) {
      used.add(candidates[0].id);
      assignments.push({ hero, gear: candidates[0] });
    } else {
      assignments.push({ hero, gear: null });
    }
  }
  return assignments;
}

function runSimulation() {
  const teamSize = Math.max(1, parseInt(document.getElementById("team-size").value, 10) || 5);
  const ownedHeroes = DATA.heroes.filter((h) => owned.heroes.has(h.id));
  const ownedPets = DATA.pets.filter((p) => owned.pets.has(p.id));
  const ownedGear = DATA.gear.filter((g) => owned.gear.has(g.id));
  const output = document.getElementById("sim-output");

  if (ownedHeroes.length === 0) {
    output.innerHTML = `<p class="empty">まず所持している英雄にチェックを入れてください。</p>`;
    return;
  }

  const teams = bestTeam(ownedHeroes, Math.min(teamSize, ownedHeroes.length));
  let html = "";
  teams.forEach((candidate, idx) => {
    const teamTags = new Set(candidate.team.flatMap((h) => h.synergy_tags || []));
    const pet = bestPet(ownedPets, teamTags);
    const gearAssignments = assignGear(ownedGear, candidate.team);
    html += `
      <div class="result-block">
        <h3>候補 ${idx + 1}(スコア ${candidate.score.total.toFixed(1)})</h3>
        <p class="score-breakdown">
          Tier合計 ${candidate.score.tierSum} / 役割多様性 +${candidate.score.roleBonus.toFixed(1)} /
          シナジー +${candidate.score.synergyBonus.toFixed(1)}
        </p>
        <ul class="team-list">
          ${candidate.team
            .map((h) => {
              const g = gearAssignments.find((a) => a.hero.id === h.id)?.gear;
              return `<li><span class="tier tier-${escapeHtml(h.tier)}">${escapeHtml(h.tier)}</span>
                ${escapeHtml(h.name)}(${escapeHtml(h.role || "-")})
                ${g ? ` — 装備: ${escapeHtml(g.name)}` : ""}</li>`;
            })
            .join("")}
        </ul>
        <p>おすすめペット: ${pet ? escapeHtml(pet.pet.name) : "所持ペットなし"}</p>
      </div>
    `;
  });
  output.innerHTML = html;
}

/* ---------- データ登録(貼り付け支援) ---------- */
function allKnownNames() {
  return CATEGORIES.flatMap((c) => DATA[c].map((item) => item.name));
}

function splitAndHighlight() {
  const text = document.getElementById("paste-input").value;
  const blocks = text.split(/\n\s*\n/).map((b) => b.trim()).filter(Boolean);
  const names = allKnownNames();
  const container = document.getElementById("paste-blocks");
  container.innerHTML = "";
  if (blocks.length === 0) {
    container.innerHTML = `<p class="empty">テキストを貼り付けてください。</p>`;
    return;
  }
  blocks.forEach((block, i) => {
    const matched = names.filter((n) => block.includes(n));
    const div = document.createElement("div");
    div.className = "paste-block";
    div.innerHTML = `
      <pre>${escapeHtml(block)}</pre>
      <p class="matched">既知データとの一致: ${matched.length ? matched.map(escapeHtml).join(", ") : "なし"}</p>
      <button type="button" data-idx="${i}" class="to-form-btn">この内容をフォームのコメント欄へ</button>
    `;
    div.querySelector(".to-form-btn").addEventListener("click", () => {
      document.getElementById("f-notes").value = block;
      document.getElementById("f-notes").scrollIntoView({ behavior: "smooth", block: "center" });
    });
    container.appendChild(div);
  });
}

function slugify(name) {
  return name
    .toLowerCase()
    .replace(/[^\p{L}\p{N}]+/gu, "-")
    .replace(/^-+|-+$/g, "") || `entry-${Date.now()}`;
}

function submitEntry(e) {
  e.preventDefault();
  const category = document.getElementById("f-category").value;
  const name = document.getElementById("f-name").value.trim();
  if (!name) return;
  const entry = {
    id: slugify(name),
    name,
    rarity: document.getElementById("f-rarity").value.trim(),
    tier: document.getElementById("f-tier").value,
    notes: document.getElementById("f-notes").value.trim(),
    source: {
      type: "discord-or-guide-manual-copy",
      detail: document.getElementById("f-source").value.trim(),
      date: new Date().toISOString().slice(0, 10),
    },
    confidence: document.getElementById("f-confidence").value,
  };
  const roleValue = document.getElementById("f-role").value.trim();
  const tags = document
    .getElementById("f-tags")
    .value.split(",")
    .map((t) => t.trim())
    .filter(Boolean);

  if (category === "gear") {
    entry.slot = roleValue;
    entry.effect = entry.notes;
    delete entry.notes;
    entry.recommended_for = tags;
  } else {
    if (category === "heroes") entry.role = roleValue;
    else entry.effect_type = roleValue;
    entry.synergy_tags = tags;
  }

  drafts.push({ category, entry });
  saveDrafts();
  renderDrafts();
  e.target.reset();
  document.getElementById("f-tier").value = "A";
}

function renderDrafts() {
  const grouped = { heroes: [], pets: [], gear: [] };
  drafts.forEach((d, idx) => grouped[d.category].push({ ...d.entry, __idx: idx }));
  const pretty = {};
  for (const c of CATEGORIES) {
    pretty[c] = grouped[c].map(({ __idx, ...rest }) => rest);
  }
  document.getElementById("draft-output").textContent =
    drafts.length === 0 ? "(ドラフトはまだありません)" : JSON.stringify(pretty, null, 2);
}

function copyAllDrafts() {
  const text = document.getElementById("draft-output").textContent;
  navigator.clipboard.writeText(text).then(() => {
    alert("コピーしました。data/heroes.json 等の該当配列に貼り付けてください。");
  });
}

function clearDrafts() {
  if (!confirm("ドラフトを全て削除します。よろしいですか？")) return;
  drafts = [];
  saveDrafts();
  renderDrafts();
}

/* ---------- 初期化 ---------- */
async function init() {
  await loadData();
  setupTabs();
  renderBrowse();
  renderOwnedCheckboxes();
  renderDrafts();

  document.getElementById("browse-category").addEventListener("change", renderBrowse);
  document.getElementById("browse-search").addEventListener("input", renderBrowse);
  document.getElementById("browse-tier").addEventListener("change", renderBrowse);
  document.getElementById("calc-btn").addEventListener("click", runSimulation);
  document.getElementById("split-btn").addEventListener("click", splitAndHighlight);
  document.getElementById("entry-form").addEventListener("submit", submitEntry);
  document.getElementById("copy-all-btn").addEventListener("click", copyAllDrafts);
  document.getElementById("clear-drafts-btn").addEventListener("click", clearDrafts);
}

init();
