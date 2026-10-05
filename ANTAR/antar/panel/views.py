"""
ANTAR panel - the page.

The look follows the operator's house language - the same plain dark
background, the same numbered sections, the same left-rail keys manager
the studio has used since V3. No gold accents, no card borders, no big
rounded rectangles. Two columns: a narrow rail for keys, a wide main
column with the title up top, section tabs underneath, and the active
section's body filling the rest.

One page, no framework, no CDN, no external font. Everything either lives
in this file or is served by the panel's own little server.
"""

from __future__ import annotations

PAGE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>ANTAR</title>
<style>
  :root {
    --bg:        #0F1115;
    --ink:       #E6E6EA;
    --muted:     #8C8C95;
    --line:      #1F2229;
    --line-2:    #2A2D34;
    --field:     #15181E;
    --hi:        'Khand', 'Nirmala UI', 'Mangal', sans-serif;
    --warn:      #C9A227;
    --bad:       #C4645A;
    --ok:        #5FA87A;
    --hi-color:  #E9E2D0;
  }
  @font-face {
    font-family: 'Khand';
    src: url('/assets/fonts/Khand-Bold.ttf') format('truetype');
    font-weight: 700; font-display: swap;
  }
  * { box-sizing: border-box; }
  html, body { height: 100%; }
  body {
    margin: 0; background: var(--bg); color: var(--ink);
    font-family: 'Segoe UI', Roboto, system-ui, sans-serif;
    font-size: 14px; line-height: 1.55;
  }

  /* ---- layout ---- */
  .app { display: grid; grid-template-columns: 230px 1fr; min-height: 100vh; }
  /* when the rail is collapsed its track must collapse too, otherwise the
     main body is squeezed into a thin strip and every tab wraps to a line */
  .app:has(aside.rail.collapsed),
  .app.rail-off { grid-template-columns: 1fr; }
  aside.rail {
    background: #0C0E11;
    border-right: 1px solid var(--line);
    padding: 18px 16px;
    font-size: 13px;
  }
  aside.rail h3 {
    margin: 0 0 4px; font-size: 13px; font-weight: 600;
    letter-spacing: .5px;
  }
  aside.rail p { margin: 0 0 14px; color: var(--muted); font-size: 12px; }
  aside.rail .row { display: flex; gap: 8px; align-items: center; margin: 6px 0; }
  aside.rail hr { border: 0; border-top: 1px solid var(--line); margin: 16px 0; }
  aside.rail ul { list-style: none; padding: 0; margin: 0; }
  aside.rail ul li { padding: 2px 0; color: var(--muted); font-size: 12px; }
  aside.rail ul li b { color: var(--ink); font-weight: 500; }
  aside.rail .foot {
    position: sticky; top: 100vh;
    margin-top: 24px; padding: 10px; background: #181C24;
    border: 1px solid var(--line); border-radius: 4px;
    color: var(--muted); font-size: 11px;
  }

  main.body { padding: 28px 36px 60px; max-width: 1180px; }
  main.body h1 {
    margin: 0 0 4px; font-size: 30px; font-weight: 700;
    letter-spacing: -.5px;
  }
  main.body h1 .sub { color: var(--muted); font-size: 14px; font-weight: 400; margin-left: 8px; }

  /* ---- section tabs ---- */
  .sections {
    border-bottom: 1px solid var(--line);
    margin: 18px 0 26px; display: flex; gap: 22px; flex-wrap: nowrap;
    overflow-x: auto; -webkit-overflow-scrolling: touch;
    scrollbar-width: thin; padding-bottom: 2px;
  }
  .sections button {
    background: none; border: 0; color: var(--muted);
    padding: 6px 2px 10px; cursor: pointer; font: inherit;
    border-bottom: 2px solid transparent;
    margin-bottom: -1px; white-space: nowrap; flex: 0 0 auto;
  }
  .sections button:hover { color: var(--ink); }
  .sections button.on { color: var(--ink); border-bottom-color: var(--bad); }

  /* ---- numbered sections ---- */
  h2.sec {
    font-size: 26px; font-weight: 700; margin: 30px 0 8px;
    letter-spacing: -.3px; color: var(--ink);
  }
  h2.sec .ico { font-size: 24px; margin-right: 8px; vertical-align: -2px; }
  h2.sec .n { color: var(--muted); font-weight: 500; margin-right: 4px; }
  h2.sec + p { margin: 0 0 18px; color: var(--muted); font-size: 13px; }
  h3.sub { color: var(--muted); font-size: 12px; font-weight: 500; margin: 14px 0 4px; letter-spacing: .4px; text-transform: uppercase; }

  /* ---- inputs ---- */
  input[type=text], input[type=number], textarea, select {
    width: 100%; background: var(--field); color: var(--ink);
    border: 1px solid var(--line-2); border-radius: 4px;
    padding: 9px 11px; font: inherit;
  }
  textarea { min-height: 92px; resize: vertical; line-height: 1.6; }
  input.hi, textarea.hi { font-family: var(--hi); font-size: 18px; }
  .two-col { display: grid; grid-template-columns: 1fr 1fr; gap: 22px; align-items: start; }
  .three-col { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 16px; align-items: start; }
  @media (max-width: 900px) {
    .app { grid-template-columns: 1fr; }
    aside.rail { border-right: 0; border-bottom: 1px solid var(--line); }
    .two-col, .three-col { grid-template-columns: 1fr; }
    main.body { padding: 18px 16px 50px; }
    main.body h1 { font-size: 24px; }
    .sections { gap: 16px; }
  }

  /* ---- buttons ---- */
  button.act {
    background: var(--field); color: var(--ink); border: 1px solid var(--line-2);
    padding: 7px 14px; border-radius: 4px; cursor: pointer; font: inherit;
  }
  button.act:hover { border-color: var(--ink); }
  button.act:disabled { opacity: .5; cursor: default; }
  button.act.primary {
    background: var(--ink); color: var(--bg); border-color: var(--ink);
  }
  button.act.primary:hover { background: #fff; }

  /* ---- tables ---- */
  table { width: 100%; border-collapse: collapse; font-size: 13px; margin-top: 6px; }
  th { text-align: left; color: var(--muted); font-weight: 500; font-size: 11px;
       letter-spacing: .6px; text-transform: uppercase; padding: 6px 10px;
       border-bottom: 1px solid var(--line); }
  td { padding: 7px 10px; border-bottom: 1px solid var(--line); vertical-align: top; }
  tr:last-child td { border-bottom: 0; }

  /* ---- status ---- */
  .st { font-weight: 600; font-size: 12px; letter-spacing: .3px; }
  .st.PASS { color: var(--ok); } .st.WARN { color: var(--warn); }
  .st.FAIL { color: var(--bad); } .st.UNAVAILABLE { color: var(--muted); }

  /* ---- console (collapsed by default) ---- */
  details.console {
    margin-top: 30px; border-top: 1px solid var(--line); padding-top: 14px;
  }
  details.console summary {
    cursor: pointer; color: var(--muted); font-size: 13px;
    list-style: none;
  }
  details.console summary::-webkit-details-marker { display: none; }
  details.console summary:hover { color: var(--ink); }
  #log {
    font-family: Consolas, 'Courier New', monospace; font-size: 12px;
    background: #08090C; border: 1px solid var(--line); border-radius: 4px;
    padding: 10px 12px; margin-top: 10px; max-height: 320px; overflow-y: auto;
    white-space: pre-wrap;
  }
  #log div { padding: 1px 0; }
  #log .m-OK { color: var(--ok); } #log .m-WARN { color: var(--warn); }
  #log .m-FAIL { color: var(--bad); } #log .m-.. { color: var(--muted); }
  #log .m-banner { color: var(--ink); } #log .m-rule { color: var(--line-2); }

  /* ---- banners ---- */
  .banner {
    padding: 9px 12px; border-radius: 4px; margin: 8px 0 14px;
    border-left: 3px solid var(--line-2); background: var(--field);
    font-size: 13px;
  }
  .banner.bad { border-left-color: var(--bad); }
  .banner.good { border-left-color: var(--ok); }
  .banner.info { border-left-color: var(--muted); }

  /* ---- pill (kept minimal, used only for live status) ---- */
  .pill { display: inline-block; padding: 2px 8px; border-radius: 999px;
          border: 1px solid var(--line-2); font-size: 11px; color: var(--muted);
          margin-right: 4px; background: var(--field); }

  /* ---- hi text ---- */
  .hi { font-family: var(--hi); color: var(--hi-color); }

  /* ---- sidebar nav ---- */
  aside.rail nav button {
    display: block; width: 100%; text-align: left;
    background: none; border: 0; color: var(--muted);
    padding: 6px 8px; cursor: pointer; font: inherit;
    border-radius: 4px;
  }
  aside.rail nav button:hover { background: #15181E; color: var(--ink); }
  aside.rail nav button.on { background: #1A1E25; color: var(--ink); }

  /* ---- helpers ---- */
  .muted { color: var(--muted); }
  .small { font-size: 12px; }
  .sep { border: 0; border-top: 1px solid var(--line); margin: 24px 0; }
  .hidden { display: none; }
  img.thumb { max-width: 280px; border: 1px solid var(--line); display: block; }
  video { width: 100%; max-width: 360px; background: #000; border: 1px solid var(--line); }

  /* ---- bar (no color, just a line) ---- */
  .bar { height: 4px; background: var(--line); border-radius: 2px; min-width: 80px; overflow: hidden; }
  .bar > div { height: 100%; background: var(--ink); }

  /* ---- rail elements (V3 style) ---- */
  .rail-head { display: flex; justify-content: flex-end; margin-bottom: 14px; }
  .rail-collapse {
    background: none; border: 0; color: var(--muted);
    cursor: pointer; font-size: 16px; padding: 2px 6px; border-radius: 4px;
  }
  .rail-collapse:hover { color: var(--ink); background: var(--field); }
  aside.rail h3 {
    font-size: 14px; font-weight: 600; margin: 0 0 6px; color: var(--ink);
  }
  aside.rail h3 .icon { margin-right: 6px; font-size: 14px; }
  aside.rail label {
    display: block; color: var(--muted); font-size: 12px;
    margin: 14px 0 4px; letter-spacing: .3px;
  }
  .grid-2 { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; margin-top: 8px; }
  .grid-2 button.act {
    padding: 8px 6px; line-height: 1.25; text-align: center;
  }
  .input-with-icon { position: relative; }
  .input-with-icon input { padding-right: 30px; }
  .input-with-icon .eye {
    position: absolute; right: 8px; top: 50%; transform: translateY(-50%);
    color: var(--muted); cursor: pointer; font-size: 13px;
    background: transparent; padding: 0 4px;
  }
  .input-with-icon .eye:hover { color: var(--ink); }
  .rail-rotation { list-style: none; padding: 0; margin: 0; font-size: 12px; }
  .rail-rotation li {
    padding: 3px 0; color: var(--ink); display: flex; gap: 6px; align-items: center;
  }
  .rail-rotation li .dot {
    width: 8px; height: 8px; border-radius: 50%;
    background: var(--muted); flex-shrink: 0;
  }
  .rail-rotation li .dot.alive { background: var(--ok); }
  .rail-rotation li .dot.dead { background: var(--bad); }
  .avoid-box {
    background: #181C24; border: 1px solid var(--line);
    border-radius: 4px; padding: 10px 12px;
    color: #5B8DBF; font-size: 12px; line-height: 1.4;
  }
  .rail-foot {
    margin-top: 24px; padding-top: 12px;
    border-top: 1px solid var(--line);
    color: var(--muted); font-size: 11px;
  }
  aside.rail.collapsed { display: none; }

  /* ---- topbar (Deploy link) ---- */
  .topbar { display: flex; justify-content: flex-end; align-items: center;
            gap: 14px; margin-bottom: 8px; }
  .topbar .deploy {
    color: var(--muted); font-size: 12px; cursor: pointer;
  }
  .topbar .deploy:hover { color: var(--ink); }
  .topbar .muted { font-size: 16px; }
</style>
</head>
<body>
<div class="app">

<aside class="rail">
  <div class="rail-head">
    <button class="rail-collapse" id="rail-collapse" title="collapse">«</button>
  </div>

  <h3><span class="icon">⚙️</span> API Key Manager</h3>
  <p>Manually add extra keys. The app will auto-test them before saving.</p>

  <div class="grid-2">
    <button class="act" id="btn-sync">📁 Sync<br><span class="muted small">.env</span></button>
    <button class="act" id="btn-purge">🧹 Auto-<br>Purge</button>
    <button class="act" id="btn-dead">💀 Dead keys<br><span class="muted small">archive</span></button>
  </div>

  <button class="act" id="btn-refresh-ai" style="margin-top:10px; width:100%; text-align:left">
    🔑 Refresh AI key
    <span class="muted small" style="margin-left:6px">one click - opens Groq, accepts your new key, runs the next video</span>
  </button>
  <div id="refresh-ai-panel" class="hidden" style="margin-top:8px; background:#181C24; border:1px solid var(--line); border-radius:4px; padding:12px; font-size:12px"></div>

  <label>Select Service</label>
  <select id="rail-service">
    <option>groq</option><option>gemini</option>
    <option>pexels</option><option>pixabay</option>
    <option>openai</option><option>anthropic</option>
    <option>elevenlabs</option><option>huggingface</option>
    <option>openrouter</option><option>together</option>
    <option>stability</option><option>removebg</option>
    <option>serpapi</option><option>deepgram</option>
    <option>replicate</option><option>youtube</option>
  </select>

  <label>Enter New API Key</label>
  <div class="input-with-icon">
    <input type="text" id="rail-key" placeholder="">
    <span class="eye" title="show / hide">👁</span>
  </div>

  <button class="act" id="btn-add-test" style="margin-top:8px">+ Add &amp; Test Key</button>

  <hr>

  <h3>Active Keys in Rotation:</h3>
  <ul id="rail-rotation" class="rail-rotation">
    <li class="muted small">no rotation yet</li>
  </ul>

  <hr>

  <h3>Active AI Avoidance Rules</h3>
  <div class="avoid-box">
    <div id="rail-avoid">The AI has not registered any fatal failures yet.</div>
  </div>

  <div class="rail-foot">
    <div>Workspace: <span id="rail-workspace">D:\\ANTAR</span></div>
    <div style="margin-top:4px">Run: <code style="color:var(--ink)">python run.py panel</code></div>
  </div>
</aside>

<main class="body">
  <div class="topbar">
    <span class="deploy" id="deploy">Deploy</span>
    <span class="muted small">⋮</span>
  </div>

  <h1 id="page-title">ANTAR: Master Studio</h1>

  <div class="sections" id="sections" data-tabs='["HOME","WRITER","PICTURE","CHECK","DETAILS","PROOF","SCORE","KEYS","LEARN","SETTINGS"]'></div>

  <div id="banner"></div>
  <div id="view"><div class="muted">loading...</div></div>

  <details class="console" id="console">
    <summary>The console (click to expand - shows exactly what the command line prints)</summary>
    <div id="log"><div class="muted">No job has run yet.</div></div>
  </details>
</main>

</div>

<script>
const TABS = [
  { id: "HOME",    label: "🏠 Home",                 hint: "Where the studio starts - one click to render a video." },
  { id: "WRITER",  label: "✍️ Writer",               hint: "Pick a topic, write a Hindi script, lock the rotation." },
  { id: "PICTURE", label: "🖼️ Picture Planner",      hint: "Pick stock footage, lay out shots, set the grade." },
  { id: "CHECK",   label: "🛡️ Self-checks",          hint: "Every rule the project committed to, with a real number behind it." },
  { id: "DETAILS", label: "🚀 YouTube SEO & Packaging", hint: "Title, description, tags, pinned comment, thumbnail." },
  { id: "PROOF",   label: "🧪 Proofs",               hint: "Every numbered test-plan item, with a real number behind it." },
  { id: "SCORE",   label: "📊 Score & Unlock",       hint: "The scorecard and the upload unlock gate." },
  { id: "KEYS",    label: "🔑 Keys",                 hint: "What is alive, what is dead, and what was never tested." },
  { id: "LEARN",   label: "🧠 Machine Learning Loop", hint: "YouTube analytics in - next topic informed by what worked." },
  { id: "SETTINGS",label: "⚙️ Settings",             hint: "Lane, rotation defaults, output paths, run mode." },
];
let tab = "HOME";
let state = { render_id: "", job: null, poll: null };
const $ = (id) => document.getElementById(id);

function esc(text) {
  return String(text === null || text === undefined ? "" : text)
    .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}
function hi(text) { return '<span class="hi">' + esc(text) + "</span>"; }
function num(value, fallback) { return (value === null || value === undefined) ? fallback : value; }

async function api(path, body) {
  const opts = body ? { method: "POST", headers: { "Content-Type": "application/json" },
                        body: JSON.stringify(body) } : {};
  const response = await fetch(path, opts);
  let payload = {};
  try { payload = await response.json(); } catch (e) { payload = { error: "the panel sent something that was not JSON" }; }
  if (!response.ok) { throw new Error(payload.error || ("request failed: " + response.status)); }
  return payload;
}

function banner(kind, text) {
  $("banner").innerHTML = text ? '<div class="banner ' + kind + '">' + esc(text) + "</div>" : "";
}

function buildSections() {
  $("sections").innerHTML = TABS.map(function (t) {
    return '<button data-tab="' + t.id + '" class="' + (t.id === tab ? "on" : "") + '" title="' + esc(t.hint) + '">' + esc(t.label) + "</button>";
  }).join("");
  Array.from($("sections").children).forEach(function (button) {
    button.onclick = function () { tab = button.dataset.tab; buildSections(); draw(); };
  });
}

function buildRailNav() {
  const navEl = $("rail-nav");
  if (!navEl) return;
  navEl.innerHTML = TABS.map(function (t) {
    return '<button data-tab="' + t.id + '" class="' + (t.id === tab ? "on" : "") + '">' + esc(t.id) + "</button>";
  }).join("");
  Array.from(navEl.children).forEach(function (button) {
    button.onclick = function () { tab = button.dataset.tab; buildSections(); buildRailNav(); draw(); window.scrollTo(0, 0); };
  });
}

async function draw() {
  try {
    const payload = await api("/api/tab/" + tab.toLowerCase() + (state.render_id ? "?render=" + encodeURIComponent(state.render_id) : ""));
    $("view").innerHTML = RENDER[tab] ? RENDER[tab](payload) : '<div class="muted">no view</div>';
    if (AFTER[tab]) { AFTER[tab](payload); }
  } catch (error) {
    $("view").innerHTML = '<div class="banner bad">' + esc(error.message) + "</div>";
  }
  refreshRail();
}

// ------------------------------------------------------------- small parts
function statusCell(row) {
  return '<span class="st ' + row.status + '">' + row.status + "</span>";
}
function bar(points, of) {
  const pct = of ? Math.round(100 * points / of) : 0;
  return '<div class="bar"><div style="width:' + pct + '%"></div></div>';
}
function emptyNote(payload, what) {
  return '<div class="banner info">' + esc(payload.note || ("nothing for " + what + " yet")) + "</div>";
}

const RENDER = {};
const AFTER = {};

// ------------------------------------------------------------------- STUDIO
RENDER.STUDIO = function (d) {
  const rows = (d.renders || []).map(function (row) {
    return "<tr><td>" + esc(row.render_id) + "</td><td>" + num(row.score, "-") + " / 100</td>" +
      "<td>" + (row.withheld ? "+" + row.withheld + " withheld" : "&mdash;") + "</td>" +
      '<td class="st ' + (row.blocked ? "FAIL" : "PASS") + '">' + (row.blocked ? "BLOCKED" : "CLEAR") + "</td>" +
      "<td class='small muted'>" + (row.has_details ? "details " : "") + (row.video_on_disk ? "video on disk" : "video packed away") + "</td></tr>";
  }).join("");
  return (
    '<h2 class="sec"><span class="n">1.</span>Content Source</h2>' +
    '<div class="two-col">' +
      '<div>' +
        '<h3 class="sub">CURRENT RENDER</h3>' +
        '<div class="hi" style="font-size:22px; margin-bottom:6px">' + esc(d.render_id || "no render yet") + "</div>" +
        '<div class="muted">' + esc(d.title || "no title yet") + "</div>" +
        '<div style="margin-top:18px; display:flex; gap:8px; flex-wrap:wrap">' +
          '<button class="act primary" id="btn-video" style="text-transform:uppercase">Make one video</button> ' +
          '<button class="act" id="btn-check">Run check</button> ' +
          '<button class="act" id="btn-details">Write details</button>' +
        '</div>' +
        '<p class="muted small" style="margin-top:14px">Topics, script, voice, picture, render, check, details - the whole run, one job at a time. The console (below) shows it live.</p>' +
      '</div>' +
      '<div>' +
        '<h3 class="sub">STATUS</h3>' +
        '<table>' +
          '<tr><td class="muted">Score</td><td><b>' + (d.score !== undefined ? d.score : "-") + '</b> / 100</td></tr>' +
          '<tr><td class="muted">Upload unlock</td><td>' + d.upload_unlock + ' &nbsp; <span class="small muted">' + (d.blocked ? "blocked by " + esc((d.blocked_by || []).join(", ")) : (d.checked ? "nothing blocking" : "not checked yet")) + '</span></td></tr>' +
          '<tr><td class="muted">Video on disk</td><td>' + (d.video_on_disk ? "<b>yes</b> - " + esc(d.video_name || "") : "<span class=\"muted\">no - shipped in ANTAR_VIDEOS.zip and deleted</span>") + '</td></tr>' +
        '</table>' +
      '</div>' +
    '</div>' +

    '<h2 class="sec"><span class="n">2.</span>Single Video Mode</h2>' +
    '<div class="muted small">Click the buttons below to run any stage. Make one video runs the whole chain. The console (below) shows every line as it runs.</div>' +
    '<div style="margin-top:14px; display:flex; gap:8px; flex-wrap:wrap">' +
      '<button class="act primary" id="btn-video-2">Make one video</button>' +
      '<button class="act" id="btn-topics">Generate Topics</button>' +
      '<button class="act" id="btn-write">Generate Script</button>' +
      '<button class="act" id="btn-voice">Build Voice</button>' +
      '<button class="act" id="btn-picture">Find Picture</button>' +
      '<button class="act" id="btn-build">Build Video</button>' +
    '</div>' +

    '<h2 class="sec"><span class="n">3.</span>Last Five</h2>' +
    '<table><tr><th>render</th><th>score</th><th>withheld</th><th>upload</th><th>on disk</th></tr>' +
    (rows || "<tr><td colspan=5 class='muted'>nothing built yet</td></tr>") + "</table>"
  );
};
AFTER.STUDIO = function () {
  const wire = function () {
    const a = $("btn-video");   if (a) a.onclick = function () { startJob("make one video", "video", {}); };
    const b = $("btn-check");   if (b) b.onclick = function () { startJob("check the video", "check", {}); };
    const c = $("btn-details"); if (c) c.onclick = function () { startJob("write the details", "details", {}); };
    const d = $("btn-video-2"); if (d) d.onclick = function () { startJob("make one video", "video", {}); };
    const e = $("btn-topics");  if (e) e.onclick = function () { startJob("choose topics", "topics", {}); };
    const f = $("btn-write");   if (f) f.onclick = function () { startJob("write the script", "write", {}); };
    const g = $("btn-voice");   if (g) g.onclick = function () { startJob("record the voice", "voice", {}); };
    const h = $("btn-picture"); if (h) h.onclick = function () { startJob("find the picture", "picture", {}); };
    const i = $("btn-build");   if (i) i.onclick = function () { startJob("render the video", "build", {}); };
  };
  wire();
};

// ----------------------------------------------------------------- DETAILS
RENDER.DETAILS = function (d) {
  if (!d.ready) { return emptyNote(d, "this render"); }
  const candidates = (d.candidates || []).map(function (row) {
    return "<tr><td>" + row.score + "</td><td>" + hi(row.title) + "</td>" +
      '<td class="small muted">' + esc(row.origin) + "</td>" +
      '<td><button class="act" data-use="' + esc(row.title) + '">use</button></td></tr>';
  }).join("");
  const audit = (d.audit || []).map(function (row) {
    return "<tr><td>" + esc(row.check) + '</td><td><span class="st ' + (row["pass"] ? "PASS" : "FAIL") + '">' + (row["pass"] ? "PASS" : "FAIL") + "</span></td>" +
      '<td class="small muted">' + esc(row.detail) + "</td></tr>";
  }).join("");
  const thumb = d.thumbnail || {};
  return (
    '<div class="two-col"><div>' +
      '<h2 class="sec"><span class="n">1.</span>The Title</h2>' +
      '<input class="hi" type="text" id="f-title" value="' + esc(d.title_hi) + '">' +
      '<div id="score-live" style="margin-top:10px"></div>' +

      '<h2 class="sec"><span class="n">2.</span>Description</h2>' +
      '<textarea id="f-desc">' + esc(d.description) + "</textarea>" +
      '<div class="muted small" style="margin-top:6px">the search phrase must sit inside the first 100 characters &middot; ' +
        (d.hashtag_rule || [3, 5]).join("-") + " hashtags</div>" +
      '<div style="margin-top:8px">' + (d.hashtags || []).map(function (tag) { return '<span class="pill hi">' + esc(tag) + "</span>"; }).join("") + "</div>" +

      '<h2 class="sec"><span class="n">3.</span>Tags <span class="muted small" style="font-weight:400">- comma separated, 10 to 15, no hashtags</span></h2>' +
      '<textarea id="f-tags" style="min-height:60px">' + esc((d.tags || []).join(", ")) + "</textarea>" +

      '<h2 class="sec"><span class="n">4.</span>Pinned Comment <span class="muted small" style="font-weight:400">- it has to be a full sentence</span></h2>' +
      '<textarea id="f-pinned" class="hi">' + esc(d.pinned_comment) + "</textarea>" +

      '<div style="margin-top:18px">' +
        '<button class="act primary" id="btn-save">Save the details</button> ' +
        '<button class="act" id="btn-regen">Generate again (live search)</button> ' +
        '<span class="small muted" id="save-state"></span>' +
      '</div>' +

      '<h2 class="sec"><span class="n">5.</span>Its Own Audit</h2>' +
      '<table><tr><th>rule</th><th></th><th>detail</th></tr>' + audit + "</table>" +
    '</div><div>' +
      '<h2 class="sec"><span class="n">6.</span>Thumbnail</h2>' +
      '<h3 class="sub">THE REAL THUMBNAIL</h3>' +
      (d.thumbnail_landscape || d.thumbnail_file
        ? '<img class="thumb" src="/media/real_thumbnail?render=' + encodeURIComponent(d.render_id) + '&t=' + Date.now() + '">' +
          '<div class="small muted" style="margin-top:8px">' +
            (d.thumbnail_landscape ? "1280x720 landscape, for the upload form. " : "") +
            (d.thumbnail_at ? "Picked at " + d.thumbnail_at.toFixed(1) + "s. " : "") +
            (d.thumbnail_in_band ? "Inside the locked band." : "Outside the locked band.") +
          "</div>"
        : '<div class="banner info">No real thumbnail on disk yet - run: python run.py proof</div>') +
      '<h3 class="sub">THE AUTO PICK</h3>' +
      '<div class="small">' + num(thumb.at, "?") + "s &middot; brightness " + num(thumb.mean, "?") + "/255 &middot; " + esc(thumb.reason || "") + "</div>" +
      '<h3 class="sub" style="margin-top:14px">PICK A DIFFERENT FRAME</h3>' +
      '<div style="display:flex; gap:8px; align-items:center">' +
        '<input type="number" id="f-second" min="0" max="90" step="0.5" value="' + num(thumb.at, 0) + '" style="width:100px">' +
        '<button class="act" id="btn-thumb">Use this frame</button>' +
      '</div>' +
      '<div class="small muted" id="thumb-state" style="margin-top:8px">' + (d.video_on_disk ? "" : "No video on disk right now, so a frame cannot be cut.") + "</div>" +

      '<h2 class="sec"><span class="n">7.</span>Candidates</h2>' +
      '<table><tr><th>score</th><th>title</th><th>written by</th><th></th></tr>' + candidates + "</table>" +

      '<h2 class="sec"><span class="n">8.</span>Harvest</h2>' +
      '<div class="small muted">' + esc(d.harvest_note || "") + "</div>" +
      '<div style="margin-top:8px">' + (d.phrases || []).slice(0, 8).map(function (p) { return '<span class="pill hi">' + esc(p) + "</span>"; }).join("") + "</div>" +
    '</div></div>');
};
AFTER.DETAILS = function () {
  const title = $("f-title");
  if (!title) return;
  let timer = null;
  function live() {
    clearTimeout(timer);
    timer = setTimeout(async function () {
      try {
        const r = await api("/api/score", { render_id: state.render_id, title: title.value });
        const parts = r.parts.map(function (p) {
          return "<tr><td>" + esc(p.part) + "</td><td>" + p.points + " / " + p.of + "</td>" +
            '<td style="width:120px">' + bar(p.points, p.of) + "</td>" +
            '<td class="small muted">' + esc(p.note) + "</td></tr>";
        }).join("");
        const cls = r.total >= r.gate ? (r.total >= r.target ? "good" : "info") : "bad";
        $("score-live").innerHTML =
          '<div class="banner ' + cls + '" style="margin-bottom:8px"><b>' + r.total + " / 100</b> &middot; gate " + r.gate +
          " &middot; generator target " + r.target + " &middot; judged against " + r.phrases_count + " harvested phrase(s) (" + esc(r.phrases_from) + ")</div>" +
          '<table><tr><th>part</th><th>points</th><th></th><th>note</th></tr>' + parts + "</table>";
      } catch (error) {
        $("score-live").innerHTML = '<div class="banner bad">' + esc(error.message) + "</div>";
      }
    }, 220);
  }
  title.oninput = live;
  live();
  Array.from(document.querySelectorAll("[data-use]")).forEach(function (button) {
    button.onclick = function () { title.value = button.dataset.use; live(); };
  });
  const save = $("btn-save"); if (save) save.onclick = async function () {
    $("save-state").textContent = "saving...";
    try {
      const tags = $("f-tags").value.split(",").map(function (t) { return t.trim(); }).filter(Boolean);
      const r = await api("/api/save", { render_id: state.render_id, title_hi: title.value,
        description: $("f-desc").value, tags: tags, pinned_comment: $("f-pinned").value });
      const bad = (r.audit || []).filter(function (row) { return !row["pass"]; });
      $("save-state").textContent = "saved";
      banner(bad.length ? "bad" : "good", bad.length
        ? "saved, but " + bad.length + " rule(s) fail: " + bad.map(function (b) { return b.check; }).join("; ")
        : "saved, and every details rule passes");
      draw();
    } catch (error) { $("save-state").textContent = ""; banner("bad", error.message); }
  };
  const regen = $("btn-regen"); if (regen) regen.onclick = function () { startJob("generate the details again", "details", { refresh: true }); };
  const thumb = $("btn-thumb"); if (thumb) thumb.onclick = async function () {
    $("thumb-state").textContent = "cutting the frame...";
    try {
      const r = await api("/api/thumbnail", { render_id: state.render_id, second: Number($("f-second").value) });
      $("thumb-state").textContent = "frame at " + r.second + "s, brightness " + r.mean + "/255" + (r.in_band ? " (inside the locked band)" : " (outside the 35-45 band - the check will say so)");
      banner("good", "manual thumbnail picked at " + r.second + "s -> " + r.path);
      draw();
    } catch (error) { $("thumb-state").textContent = ""; banner("bad", error.message); }
  };
};

// ------------------------------------------------------------------- SCORE
RENDER.SCORE = function (d) {
  if (!d.ready) { return emptyNote(d, "this render"); }
  const rows = (d.categories || []).map(function (row) {
    const ok = row.points >= row.of;
    return "<tr><td>" + esc(row.name) + "</td><td>" + row.points + " / " + row.of + "</td>" +
      '<td style="width:160px">' + bar(row.points, row.of) + "</td>" +
      '<td class="small muted">' + esc(row.note || "") + "</td></tr>";
  }).join("");
  const withheld = (d.withheld || []).map(function (w) {
    return "<tr><td>" + esc(w.name) + "</td><td>" + w.points + "</td><td class='small muted'>" + esc(w.note || "") + "</td></tr>";
  }).join("");
  return (
    '<div class="three-col">' +
      '<div><h3 class="sub">MEASURED</h3><div style="font-size:30px">' + num(d.total, 0) + ' <span class="muted small" style="font-size:14px">/ 100</span></div><div class="muted small">' + num(d.measured_of, 100) + ' points could be measured</div></div>' +
      '<div><h3 class="sub">WITHHELD</h3><div style="font-size:30px">' + num(d.withheld_points, 0) + '</div><div class="muted small">' + (withheld ? "parts of the score that need a phase that does not exist yet" : "nothing withheld") + "</div></div>" +
      '<div><h3 class="sub">UPLOAD UNLOCK</h3><div style="font-size:30px">' + d.upload_unlock + '</div><div class="muted small">' + (d.blocked_from_upload ? "blocked: " + esc((d.blocked_by || []).join(", ")) : "nothing blocking") + "</div></div>" +
    '</div>' +
    '<h2 class="sec"><span class="n">1.</span>The Breakdown</h2>' +
    '<table><tr><th>category</th><th>points</th><th></th><th>what it measured</th></tr>' + rows + "</table>" +
    (withheld ? '<h2 class="sec"><span class="n">2.</span>Withheld</h2><div class="table"><table><tr><th>category</th><th>points</th><th>why</th></tr>' + withheld + "</table></div>" : ""));
};

// ------------------------------------------------------------------- PROOFS
RENDER.PROOFS = function (d) {
  if (!d.ready) { return emptyNote(d, "this render"); }
  const s = d.summary || {};
  const row = function (check) {
    return "<tr><td>" + esc(check.name) + "</td>" +
      '<td><span class="st ' + check.result + '">' + check.result + "</span></td>" +
      '<td class="small">' + esc(check.measured) + "</td>" +
      '<td class="small muted">' + esc(check.target || "") + "</td>" +
      '<td class="small muted">' + esc(check.note || "") + "</td></tr>";
  };
  const verdict = s.verdict || "";
  const card = (s.categories || []).map(function (row) {
    return "<tr><td>" + esc(row.category) + "</td><td>" + row.earned + " / " + row.of + "</td>" +
      '<td style="width:160px">' + bar(row.earned, row.of) + "</td></tr>";
  }).join("");
  return (
    '<div style="margin-bottom:16px">' +
      '<span class="pill">' + esc(d.score || 0) + ' / 100</span>' +
      '<span class="pill">gate ' + d.gate + '</span>' +
      '<span class="pill">' + d.passed + ' pass</span>' +
      '<span class="pill">' + d.warned + ' warn</span>' +
      '<span class="pill">' + d.failed + ' fail</span>' +
      '<span class="pill">' + d.unavailable + ' unavailable</span>' +
      ' <button class="act" id="btn-proof" style="margin-left:8px">Run the proof stage</button>' +
    '</div>' +
    (d.gate_cleared
      ? '<div class="banner good">' + esc(verdict) + "</div>"
      : '<div class="banner bad">' + esc(verdict) + "</div>") +
    (d.withheld ? '<div class="banner info">' + d.withheld + ' point(s) withheld - ' +
      esc((s.withheld_categories || []).join(", ")) +
      "; the upload unlock does not need them today</div>" : "") +
    '<h2 class="sec"><span class="n">1.</span>Every Proof in the Test Plan</h2>' +
    '<table><tr><th>check</th><th>result</th><th>measured</th><th>target</th><th>note</th></tr>' +
    (d.checks || []).map(row).join("") + "</table>" +
    '<h2 class="sec"><span class="n">2.</span>The Scorecard This Proof Reads</h2>' +
    '<table><tr><th>category</th><th>points</th><th></th></tr>' + card + "</table>" +
    '<div class="small muted" style="margin-top:14px">evidence file: ' + esc((s.evidence || "") + " &middot; " + (d.evidence || "")) + "</div>");
};
AFTER.PROOFS = function () { const b = $("btn-proof"); if (b) b.onclick = function () { startJob("proof stage", "proof", {}); }; };

// ------------------------------------------------------------------- LEARN
RENDER.LEARN = function (d) {
  if (!d.ready) {
    return '<div class="banner info">' + esc(d.note || "no analytics yet") + "</div>" +
      '<div class="muted small" style="margin-top:6px">This tab will show:</div>' +
      '<ul style="margin-top:8px">' +
      (d.will_show || []).map(function (item) { return '<li class="small muted">' + esc(item) + "</li>"; }).join("") +
      '</ul>' +
      '<h2 class="sec"><span class="n">1.</span>Upload a YouTube Studio CSV</h2>' +
      '<input type="file" id="learn-file" accept=".csv">' +
      '<div style="margin-top:10px">' +
        '<button class="act primary" id="learn-upload">Import &amp; run the loop</button>' +
        '<span class="small muted" id="learn-status" style="margin-left:10px"></span>' +
      '</div>';
  }
  const axisRows = function (rows) {
    return (rows || []).map(function (row) {
      const cls = row.trusted ? "PASS" : "UNAVAILABLE";
      return "<tr><td>" + esc(row.name) + "</td>" +
        '<td><span class="st ' + cls + '">' + (row.trusted ? "TRUSTED" : "few videos") + "</span></td>" +
        '<td>' + row.score.toFixed(1) + "</td>" +
        '<td>' + row.videos + "</td>" +
        '<td>' + row.retention_pct.toFixed(1) + '%</td>' +
        '<td>' + row.views_per_video.toFixed(0) + "</td>" +
        '<td>' + row.swipe_away_pct.toFixed(1) + '%</td></tr>';
    }).join("");
  };
  const axes = d.axes || {};
  const brief = d.next_topic_brief;
  const ap = d.anti_patterns || [];
  return (
    '<div style="margin-bottom:14px">' +
      '<span class="pill">' + (d.csvs || []).length + ' CSV(s)</span>' +
      '<span class="pill">' + (d.videos_with_data || 0) + " videos with data</span>" +
      ' <button class="act" id="btn-learn" style="margin-left:8px">Run the learn stage</button>' +
    '</div>' +
    (d.note ? '<div class="banner info">' + esc(d.note) + "</div>" : "") +
    '<h2 class="sec"><span class="n">1.</span>Next Topic Brief</h2>' +
    (brief && brief.lane
      ? '<table>' +
          (["lane", "hook", "structure", "grade"]).map(function (axis) {
            const row = brief[axis];
            if (!row) return "";
            return '<tr><td class="muted" style="width:120px">' + axis + '</td><td>' + esc(row.name) +
              ' <span class="small muted">retention ' + row.retention_pct.toFixed(1) + '%, ' +
              row.videos + ' video(s)</span></td></tr>';
          }).join("") +
        '</table>'
      : '<div class="banner info">the brief needs at least two videos with analytics on file</div>') +
    '<h2 class="sec"><span class="n">2.</span>Rankings</h2>' +
    '<table><tr><th>axis</th><th>name</th><th>score</th><th>videos</th><th>retention</th><th>views/video</th><th>swipe-away</th></tr>' +
    Object.keys(axes).map(function (axis) {
      return "<tr><td colspan=7><b>" + axis + "</b></td></tr>" +
        axisRows(axes[axis]);
    }).join("") + "</table>" +
    (ap.length
      ? '<h2 class="sec"><span class="n">3.</span>Anti-patterns <span class="muted small" style="font-weight:400">- avoid these next time</span></h2>' +
        '<table>' +
        ap.map(function (row) { return "<tr><td>" + esc(row.axis) + "</td><td>" + esc(row.name) + "</td>" +
          '<td>' + row.score.toFixed(1) + "</td><td>" + row.videos + "</td></tr>"; }).join("") +
        "</table>"
      : ""));
};
AFTER.LEARN = function () {
  const btn = $("btn-learn");
  if (btn) btn.onclick = function () { startJob("learn stage", "learn", {}); };
  const upload = $("learn-upload");
  if (upload) upload.onclick = async function () {
    const file = $("learn-file").files[0];
    if (!file) { $("learn-status").textContent = "choose a CSV first"; return; }
    $("learn-status").textContent = "uploading...";
    try {
      await api("/api/learn/import", { source: file.name });
      $("learn-status").textContent = "imported, running the loop";
      const r = await api("/api/learn/run");
      $("learn-status").textContent = r.ran ? "learn stage ran; refreshing" : r.note;
      draw();
    } catch (error) {
      $("learn-status").textContent = error.message;
    }
  };
};

// -------------------------------------------------------------------- KEYS
RENDER.KEYS = function (d) {
  const rows = (d.keys || []).map(function (key) {
    const cls = key.state === "alive" ? "PASS" : (key.state === "dead" ? "FAIL" : "UNAVAILABLE");
    return "<tr><td>" + esc(key.service) + "</td><td>" + esc(key.masked) + '</td><td><span class="st ' + cls + '">' + esc(key.state) + "</span></td>" +
      '<td class="small muted">' + esc(key.reason || "") + "</td><td>" + num(key.uses, 0) + "</td><td>" + num(key.fails, 0) + "</td>" +
      "<td>" + (key.has_test ? "" : '<span class="small muted">no test written</span>') + "</td></tr>";
  }).join("");
  return (
    '<div style="margin-bottom:14px">' +
      '<span class="pill">' + num(d.count, 0) + " keys</span>" +
      '<span class="pill">' + num(d.alive, 0) + " alive</span>" +
      '<span class="pill">' + num(d.dead, 0) + " dead, kept</span>" +
      ' <button class="act" id="btn-keys" style="margin-left:8px">Test them again</button>' +
    '</div>' +
    '<div class="muted small" style="margin-bottom:10px">' + esc(d.note) + "</div>" +
    '<table><tr><th>service</th><th>key</th><th>state</th><th>what the service said</th><th>uses</th><th>fails</th><th></th></tr>' + rows + "</table>" +
    (d.without_a_test && d.without_a_test.length
      ? '<div class="banner info" style="margin-top:14px">No test written for: ' + esc(d.without_a_test.join(", ")) + " &mdash; kept on file, never called dead.</div>" : "") +
    '<div class="small muted" style="margin-top:10px">Checked live by the key checker: ' + esc((d.checked_services || []).join(", ")) + "</div>");
};
AFTER.KEYS = function () { const b = $("btn-keys"); if (b) b.onclick = function () { startJob("test the keys", "keys", {}); }; };

// ---------------------------------------------------------------- WRITER
RENDER.WRITER = function (d) {
  if (!d.ready) {
    return (
      emptyNote(d, "writer") +
      '<div style="margin-top:14px; display:flex; gap:8px; flex-wrap:wrap">' +
        '<button class="act primary" id="btn-topics">Generate Topics</button>' +
        '<button class="act" id="btn-topics-off">Topics (offline pool)</button>' +
        '<button class="act" id="btn-write">Generate Script</button>' +
        '<button class="act" id="btn-write-off">Script (offline)</button>' +
      '</div>' +
      '<p class="muted small" style="margin-top:10px">Topics first, then script. Offline uses hand-verified pool when all AI keys are dead.</p>'
    );
  }
  const beats = (d.beats || []).map(function (b) {
    return '<tr><td>' + b.n + '</td><td>' + esc(b.role || '') + '</td><td class="hi">' + esc(b.line_hi || '') + '</td><td class="small muted">' + esc(b.object_hi || '') + (b.is_peak ? ' <b>★ peak</b>' : '') + '</td></tr>';
  }).join("");
  return (
    '<div class="two-col"><div>' +
      '<h2 class="sec"><span class="n">1.</span>Current Script</h2>' +
      '<div class="hi" style="font-size:20px">' + esc(d.title_hi || d.topic_title || "") + '</div>' +
      '<div class="muted small" style="margin-top:6px">search: ' + esc(d.search_phrase_hi || "") + ' &middot; mechanism: ' + esc(d.mechanism_hi || "") + '</div>' +
      '<div class="muted small">words: ' + num(d.words, "-") + ' &middot; beats: ' + num(d.beats_count, "-") + ' &middot; structure: ' + esc(d.structure || "") + ' &middot; hook: ' + esc(d.hook_angle || "") + '</div>' +
      '<div style="margin-top:14px; display:flex; gap:8px; flex-wrap:wrap">' +
        '<button class="act primary" id="btn-write">Generate Script</button>' +
        '<button class="act" id="btn-write-off">Script (offline)</button>' +
        '<button class="act" id="btn-topics">Generate Topics</button>' +
        '<button class="act" id="btn-topics-off">Topics (offline)</button>' +
        '<button class="act" id="btn-voice">Build Voice</button>' +
      '</div>' +
      '<h2 class="sec"><span class="n">2.</span>Beats</h2>' +
      '<table><tr><th>#</th><th>role</th><th>line</th><th>object</th></tr>' + beats + '</table>' +
    '</div><div>' +
      '<h3 class="sub">Rotation used</h3>' +
      '<code class="small">' + esc(JSON.stringify(d.rotation || {}, null, 2)) + '</code>' +
      (d.closing_echo ? '<h3 class="sub" style="margin-top:14px">Closing echo</h3><div class="hi">' + esc(d.closing_echo) + '</div>' : '') +
    '</div></div>'
  );
};
AFTER.WRITER = function () {
  const a = $("btn-topics"); if (a) a.onclick = function () { startJob("choose topics", "topics", {}); };
  const b = $("btn-topics-off"); if (b) b.onclick = function () { startJob("choose topics offline", "topics", { offline: true }); };
  const c = $("btn-write"); if (c) c.onclick = function () { startJob("write the script", "write", {}); };
  const d = $("btn-write-off"); if (d) d.onclick = function () { startJob("write offline", "write", { offline: true }); };
  const e = $("btn-voice"); if (e) e.onclick = function () { startJob("record the voice", "voice", {}); };
};

// --------------------------------------------------------------- PICTURE
RENDER.PICTURE = function (d) {
  if (!d.ready) {
    return (
      emptyNote(d, "picture") +
      '<div style="margin-top:14px; display:flex; gap:8px; flex-wrap:wrap">' +
        '<button class="act primary" id="btn-picture">Find Picture</button>' +
        '<button class="act" id="btn-voice">Build Voice First</button>' +
        '<button class="act" id="btn-build">Build Video</button>' +
      '</div>'
    );
  }
  const h = d.health || {};
  const shots = (d.shots || []).map(function (s) {
    return '<tr><td>' + num(s.index, "") + '</td><td>' + esc(s.kind || "") + '</td><td>' + esc(s.object_hi || "") + '</td><td class="small muted">' + esc(s.query || "") + '</td><td>' + esc(s.clip_id || "") + '</td><td>' + (s.start !== undefined ? s.start.toFixed(1) + "-" + (s.end || 0).toFixed(1) + "s" : "") + '</td></tr>';
  }).join("");
  return (
    '<h2 class="sec"><span class="n">1.</span>Health</h2>' +
    '<table><tr><td class="muted">Clips</td><td>' + num(h.clips, 0) + '</td><td class="muted">Cards</td><td>' + num(h.cards, 0) + '</td><td class="muted">Clip %</td><td>' + num(h.clip_pct, 0) + '%</td><td class="muted">Reused</td><td>' + num(h.reused, 0) + '</td><td class="muted">Distinct</td><td>' + num(h.distinct_clips, 0) + '</td></tr></table>' +
    '<div style="margin-top:12px; display:flex; gap:8px; flex-wrap:wrap">' +
      '<button class="act primary" id="btn-picture">Find Picture Again</button>' +
      '<button class="act" id="btn-voice">Rebuild Voice</button>' +
      '<button class="act" id="btn-build">Build Video</button>' +
    '</div>' +
    '<h2 class="sec"><span class="n">2.</span>Shots</h2>' +
    '<table><tr><th>#</th><th>kind</th><th>object</th><th>query</th><th>clip</th><th>window</th></tr>' + shots + '</table>'
  );
};
AFTER.PICTURE = function () {
  const a = $("btn-picture"); if (a) a.onclick = function () { startJob("find the picture", "picture", {}); };
  const b = $("btn-voice"); if (b) b.onclick = function () { startJob("record the voice", "voice", {}); };
  const c = $("btn-build"); if (c) c.onclick = function () { startJob("render the video", "build", {}); };
};

// ----------------------------------------------------------------- CHECK
RENDER.CHECK = function (d) {
  if (!d.ready) {
    return (
      emptyNote(d, "check") +
      '<div style="margin-top:14px"><button class="act primary" id="btn-check">Run Self-Checks</button></div>'
    );
  }
  const rows = (d.checks || []).map(function (c) {
    const cls = c.status || c.result || "UNAVAILABLE";
    return '<tr><td>' + esc(c.name || "") + '</td><td><span class="st ' + cls + '">' + cls + '</span></td><td class="small">' + esc(c.measured || "") + '</td><td class="small muted">' + esc(c.target || c.detail || "") + '</td></tr>';
  }).join("");
  const sc = d.scorecard || {};
  return (
    '<div style="margin-bottom:12px">' +
      '<span class="pill">' + num(sc.total, 0) + ' / 100</span>' +
      '<span class="pill">' + (d.blocked_from_upload ? "BLOCKED" : "CLEAR") + '</span>' +
      (d.blocked_by && d.blocked_by.length ? '<span class="pill bad">' + esc(d.blocked_by.join(", ")) + '</span>' : '') +
      ' <button class="act" id="btn-check" style="margin-left:8px">Run Again</button>' +
      ' <button class="act" id="btn-details" style="margin-left:4px">Write Details</button>' +
      ' <button class="act" id="btn-proof" style="margin-left:4px">Run Proofs</button>' +
    '</div>' +
    '<h2 class="sec"><span class="n">1.</span>Every Check</h2>' +
    '<table><tr><th>check</th><th>result</th><th>measured</th><th>target / detail</th></tr>' + rows + '</table>'
  );
};
AFTER.CHECK = function () {
  const a = $("btn-check"); if (a) a.onclick = function () { startJob("check the video", "check", {}); };
  const b = $("btn-details"); if (b) b.onclick = function () { startJob("write the details", "details", {}); };
  const c = $("btn-proof"); if (c) c.onclick = function () { startJob("proof stage", "proof", {}); };
};

// ----------------------------------------------------------- alias renders
// The TABS list uses HOME / WRITER / PICTURE / CHECK / SCORE / SETTINGS
// (10 tabs in total). Without aliases the placeholder "no view" appears.

RENDER.HOME = RENDER.STUDIO;
AFTER.HOME = AFTER.STUDIO;
RENDER.PROOF = RENDER.PROOFS;
AFTER.PROOF = AFTER.PROOFS;
AFTER.SCORE = function () {
  const b = $("btn-proof"); if (b) b.onclick = function () { startJob("proof stage", "proof", {}); };
};
AFTER.SETTINGS = function () {};
AFTER.STUDIO = AFTER.STUDIO;
RENDER.SETTINGS = function (d) {
  const v = d.voice || {};
  const t = d.type || {};
  const f = d.fixed || [];
  const rot = d.rotating || {};
  const prev = d.last_rotation || {};
  return (
    '<h2 class="sec"><span class="n">1.</span>Lane &amp; voice</h2>' +
    '<table>' +
      '<tr><td class="muted">Lane id</td><td><b>' + esc(d.lane && d.lane.id || "-") + '</b> &nbsp; <span class="small muted">' + esc(d.lane && d.lane.name || "") + '</span></td></tr>' +
      '<tr><td class="muted">Voice</td><td>' + esc(v.voice || "-") + ' &nbsp; rate ' + esc(v.rate || "-") + ' &nbsp; pitch ' + esc(v.pitch || "-") + '</td></tr>' +
      '<tr><td class="muted">Type font</td><td>' + esc(t.font || "-") + ' &nbsp; size ' + esc(t.size || "-") + '</td></tr>' +
    '</table>' +
    '<h2 class="sec"><span class="n">2.</span>Rotation defaults</h2>' +
    '<table>' +
      '<tr><td class="muted">Fixed</td><td>' + (f.length ? esc(f.join(", ")) : "<span class=muted>none</span>") + '</td></tr>' +
      '<tr><td class="muted">Rotating</td><td>' + esc(Object.keys(rot).join(", ") || "none") + '</td></tr>' +
      '<tr><td class="muted">Last rotation</td><td><code class="small">' + esc(JSON.stringify(prev, null, 0) || "no rotation on file") + '</code></td></tr>' +
    '</table>' +
    '<h2 class="sec"><span class="n">3.</span>Workshop</h2>' +
    '<table>' +
      '<tr><td class="muted">ffmpeg</td><td><code>' + esc(d.ffmpeg || "not found") + '</code></td></tr>' +
      '<tr><td class="muted">Render counter</td><td>' + esc(String(d.render_counter || 0)) + '</td></tr>' +
      '<tr><td class="muted">Paths</td><td><code class="small">' +
        Object.keys(d.paths || {}).map(function (k) { return esc(k) + " = " + esc(d.paths[k]); }).join("<br>") +
      '</code></td></tr>' +
    '</table>' +
    '<p class="muted small" style="margin-top:14px">every key tested - see the table in the API Key Manager</p>'
  );
};

// ------------------------------------------------------------------- jobs
function logLine(line) {
  const m = line.match(/\[(OK|WARN|FAIL|INFO|\.\.|>>)\]/);
  const cls = m ? ("m-" + (m[1] === "INFO" ? ".." : m[1])) : "m-..";
  const div = document.createElement("div");
  div.className = cls;
  div.textContent = line;
  $("log").appendChild(div);
  $("log").scrollTop = $("log").scrollHeight;
}

async function startJob(title, what, options) {
  console.log("ANTAR startJob", what, options);
  banner("info", "starting " + title + " - watch the console below...");
  try {
    const job = await api("/api/run", Object.assign({ what: what, render_id: state.render_id }, options || {}));
    $("log").innerHTML = "";
    logLine("[INFO] job " + job.id + " started: " + title + " (" + what + ")");
    document.getElementById("console").open = true;
    follow(job.id, title, what);
  } catch (error) {
    console.error("startJob failed", error);
    banner("bad", error.message);
    // also show in console so "No job has run yet" disappears
    if ($("log").textContent.includes("No job has run yet")) { $("log").innerHTML = ""; }
    logLine("[FAIL] could not start " + title + ": " + error.message);
    document.getElementById("console").open = true;
  }
}

async function follow(jobId, title, what) {
  clearInterval(state.poll);
  let since = 0;
  state.poll = setInterval(async function () {
    let job;
    try { job = await api("/api/job/" + jobId + "?since=" + since); }
    catch (error) { clearInterval(state.poll); banner("bad", error.message); logLine("[FAIL] poll failed: " + error.message); return; }
    (job.lines || []).forEach(logLine);
    since = job.since;
    if (job.state !== "running") {
      clearInterval(state.poll);
      if (job.state === "failed") { banner("bad", job.error || "the job failed"); }
      else { banner("good", title + " finished in " + job.seconds + "s"); }
      // for keys job, also refresh the little rail table immediately
      if (what === "keys" || title.toLowerCase().includes("keys")) {
        try {
          const k = await api("/api/tab/keys");
          showKeyTestResult({ keys: k });
        } catch (e) { /* ignore */ }
      }
      draw();
    }
  }, 700);
}

async function refreshRail() {
  try {
    const s = await api("/api/state");
    state.render_id = s.render_id || state.render_id;

    const k = await api("/api/tab/keys");
    const sets = await api("/api/tab/settings");

    // combine keys + rotation into the rail-rotation list (matches V3 layout)
    const items = [];
    (k.keys || []).forEach(function (key) {
      const dotClass = key.state === "alive" ? "alive" : (key.state === "dead" ? "dead" : "");
      items.push('<li><span class="dot ' + dotClass + '"></span>' + esc(key.service) + ': ' + esc(key.masked) + '</li>');
    });
    Object.keys(sets.rotating || {}).forEach(function (name) {
      const used = (sets.last_rotation || {})[name];
      if (used) items.push('<li><span class="dot alive"></span>' + esc(name) + ': ' + esc(used) + '</li>');
    });
    $("rail-rotation").innerHTML = items.join("") || '<li class="muted small">no rotation yet</li>';
  } catch (error) { /* rail stays as it was */ }
}

// ---- rail button actions ----
const eye = $("rail-key"); if (eye) eye.type = "password";
const eyeToggle = document.querySelector(".input-with-icon .eye");
if (eyeToggle && eye) eyeToggle.onclick = function () { eye.type = eye.type === "password" ? "text" : "password"; };

const btnSync = $("btn-sync"); if (btnSync) btnSync.onclick = async function () {
  try {
    const r = await api("/api/keys/sync", {});
    banner("good", "synced .env into keys.json");
    refreshRail();
    showKeyTestResult(r);
  } catch (e) { banner("bad", e.message); }
};
const btnPurge = $("btn-purge"); if (btnPurge) btnPurge.onclick = function () {
  // Use the job queue so the console (below) streams live, just like
  // "Make one video" does. The old code called /api/keys/test directly,
  // which blocked the HTTP request for 1-2 minutes and never touched
  // the console - that's why it said "No job has run yet".
  banner("info", "testing every key against the live API - this can take 1-2 minutes, watch the console below...");
  startJob("test the keys", "keys", {});
};

const btnDead = $("btn-dead"); if (btnDead) btnDead.onclick = async function () {
  try {
    const r = await api("/api/keys/quarantine", {});
    showKeyQuarantine(r);
  } catch (e) { banner("bad", e.message); }
};

// Render the dead-keys archive as a compact list. The active ring only
// shows alive keys, so this is where you go to see what got retired.
async function showKeyQuarantine(r) {
  let target = $("rail-key-test-result");
  if (!target) {
    target = document.createElement("div");
    target.id = "rail-key-test-result";
    target.style.cssText = "margin-top:10px; font-size:11px; line-height:1.5";
    const anchor = $("btn-refresh-ai");
    if (anchor && anchor.parentNode) anchor.parentNode.insertBefore(target, anchor.nextSibling);
  }
  if (!r || !r.count) {
    target.innerHTML = '<div class="muted">no dead keys archived</div>';
    return;
  }
  const rows = r.keys.map(function (k) {
    return '<div style="display:flex; gap:6px; align-items:center; padding:2px 0">' +
      '<span class="dot dead"></span>' +
      '<span style="min-width:78px">' + esc(k.service) + '</span>' +
      '<span style="color:var(--muted); font-size:10px">' + esc(k.masked) + '</span>' +
      '</div>' +
      '<div style="margin-left:24px; font-size:10px; color:var(--muted); margin-bottom:4px">' + esc((k.reason || '').slice(0, 60)) + '</div>';
  }).join("");
  target.innerHTML =
    '<div style="margin-bottom:4px">archived dead keys: <span style="color:var(--bad)">' + r.count + '</span></div>' + rows +
    '<div class="muted" style="margin-top:6px; font-size:10px">stored in keys_dead.json</div>';
}

// Render the test result in the rail as a compact table, so the operator
// can see which keys are alive / dead without scrolling the main view.
async function showKeyTestResult(r) {
  let keys = [];
  if (r && Array.isArray(r.keys && r.keys.keys ? r.keys.keys : r.keys)) {
    keys = r.keys.keys || [];
  } else if (r && r.keys && Array.isArray(r.keys.keys)) {
    keys = r.keys.keys;
  } else if (r && r.keys && Array.isArray(r.keys)) {
    keys = r.keys;
  }
  let target = $("rail-key-test-result");
  if (!target) {
    target = document.createElement("div");
    target.id = "rail-key-test-result";
    target.style.cssText = "margin-top:10px; font-size:11px; line-height:1.5";
    const anchor = $("btn-refresh-ai");
    if (anchor && anchor.parentNode) anchor.parentNode.insertBefore(target, anchor.nextSibling);
  }
  if (!keys.length) {
    target.innerHTML = '<div class="muted">no keys on file - add one above</div>';
    return;
  }
  const rows = keys.map(function (k) {
    const dotClass = k.state === "alive" ? "alive" : (k.state === "dead" ? "dead" : "");
    return '<div style="display:flex; gap:6px; align-items:center; padding:2px 0">' +
      '<span class="dot ' + dotClass + '"></span>' +
      '<span style="min-width:78px">' + esc(k.service) + '</span>' +
      '<span style="color:var(--muted); font-size:10px">' + esc(k.masked) + '</span>' +
      '<span style="margin-left:auto">' + esc(k.state) + '</span>' +
      '</div>';
  }).join("");
  const tally = { alive: 0, dead: 0 };
  keys.forEach(function (k) {
    if (k.state === "alive") tally.alive++;
    else if (k.state === "dead") tally.dead++;
  });
  target.innerHTML =
    '<div style="margin-bottom:4px; color:var(--muted)">last test:</div>' +
    '<div style="color:' + (tally.alive ? "var(--ok)" : "var(--bad)") + '">' +
    tally.alive + ' alive / ' + tally.dead + ' dead' +
    '</div>' + rows;
}
const btnAddTest = $("btn-add-test"); if (btnAddTest) btnAddTest.onclick = async function () {
  const service = $("rail-service").value;
  const value = $("rail-key").value;
  if (!value) { banner("bad", "paste a key first"); return; }
  try {
    await api("/api/keys/add", { service: service, value: value });
    $("rail-key").value = "";
    banner("good", "added and tested " + service);
    refreshRail();
  } catch (e) { banner("bad", e.message); }
};
const collapse = $("rail-collapse"); if (collapse) collapse.onclick = function () {
  const rail = document.querySelector("aside.rail");
  const app = document.querySelector(".app");
  rail.classList.toggle("collapsed");
  // class on the grid itself = fallback for browsers without :has()
  if (app) app.classList.toggle("rail-off", rail.classList.contains("collapsed"));
  collapse.textContent = rail.classList.contains("collapsed") ? "»" : "«";
};
const deployBtn = $("deploy"); if (deployBtn) deployBtn.onclick = function () {
  banner("info", "Deploy runs python run.py publish - wired in a later step.");
};

// ----------------- AI key refresh (one click, end to end) -----------------
// When the writer can't reach any AI, this walks the user from "I am stuck"
// to "the next video is rendering" without leaving the panel.
const btnRefreshAI = $("btn-refresh-ai");
if (btnRefreshAI) btnRefreshAI.onclick = async function () {
  const panel = $("refresh-ai-panel");
  panel.classList.remove("hidden");
  panel.innerHTML = '<div class="muted small">checking which AI keys are alive...</div>';

  let state, vendorInfo;
  try {
    state = await api("/api/keys/health");
    vendorInfo = await api("/api/keys/vendor-url");
  } catch (e) { panel.innerHTML = '<div class="muted small">' + esc(e.message) + "</div>"; return; }

  // LLM vendors the user might need a key for. Order matters: free
  // vendors first since the user is more likely to have those, and
  // we want the panel to point at a working free path before asking
  // them to spend money.
  const LLM_ORDER = ["groq", "gemini", "openrouter", "huggingface",
                     "together", "openai", "anthropic"];

  // count alive and dead keys per vendor
  const tally = {};
  for (const svc of LLM_ORDER) {
    const list = (state[svc] || []);
    tally[svc] = {
      alive: list.filter(function (k) { return k.state === "alive"; }).length,
      dead:  list.filter(function (k) { return k.state === "dead";  }).length,
      unknown: list.filter(function (k) { return k.state === "unknown"; }).length,
      total: list.length,
    };
  }

  const aliveTotal = LLM_ORDER.reduce(function (s, k) { return s + tally[k].alive; }, 0);

  if (aliveTotal > 0) {
    // show the user which vendors are alive, and which need attention
    const rows = LLM_ORDER.filter(function (s) { return tally[s].total > 0; })
      .map(function (s) {
        const t = tally[s];
        const dot = t.alive > 0 ? "ok" : (t.dead > 0 ? "bad" : "");
        return '<div style="display:flex; gap:6px; align-items:center; padding:2px 0">' +
          '<span class="dot ' + dot + '"></span>' +
          '<span style="min-width:80px">' + s + '</span>' +
          '<span style="color:var(--muted)">' + t.alive + ' alive / ' +
          t.dead + ' dead' + (t.unknown ? ' / ' + t.unknown + ' unknown' : '') + '</span>' +
          '</div>';
      }).join("");
    panel.innerHTML =
      '<div style="color:var(--ok); margin-bottom:8px">✓ You have ' + aliveTotal +
        ' working AI key(s). Click MAKE ONE VIDEO on the STUDIO tab.</div>' +
      rows;
    return;
  }

  // No alive LLM key. Pick the first vendor the user has a key for
  // (dead, unknown, or tried-this-run) - the one that probably needs
  // replacing. If the user has no keys on file at all, default to Groq.
  const preferred = LLM_ORDER.find(function (s) { return tally[s].total > 0; })
                  || "groq";
  const vendor = vendorInfo.vendors.find(function (v) { return v.service === preferred; })
              || vendorInfo.vendors[0];

  // Build a dropdown of all vendors so the user can override.
  const vendorOptions = vendorInfo.vendors
    .filter(function (v) { return v.service !== "elevenlabs"; })   // 11labs is TTS, not LLM
    .map(function (v) {
      const tag = tally[v.service] ? ' (' + tally[v.service].alive + '/' + tally[v.service].total + ')' : '';
      const free = v.free ? " (free)" : " (paid)";
      const sel  = v.service === vendor.service ? " selected" : "";
      return '<option value="' + v.service + '"' + sel + '>' + v.name + free + tag + '</option>';
    }).join("");

  panel.innerHTML =
    '<div style="margin-bottom:10px">' +
      '<b>Step 1.</b> Pick the vendor below. Click the button to open its key page. ' +
      'Sign in (one time, ~30 seconds). Click <b>Create API Key</b>, copy it.</div>' +
    '<label style="font-size:11px">Vendor:</label>' +
    '<select id="refresh-ai-vendor" style="width:100%; margin-bottom:8px">' +
      vendorOptions + '</select>' +
    '<button class="act primary" id="btn-open-vendor" style="margin-bottom:12px; width:100%">' +
      '🌐 Open ' + esc(vendor.name) + ' &amp; create a key</button>' +
    '<div style="margin-bottom:10px"><b>Step 2.</b> ' +
      'Come back here and click the paste button. The panel will grab your clipboard automatically.</div>' +
    '<button class="act primary" id="btn-paste-key" style="margin-bottom:12px">' +
      '📋 Paste my new key from clipboard</button>' +
    '<div id="refresh-ai-status" class="muted small"></div>';

  // Wire the dropdown to update the open-button label and URL.
  const sel = $("refresh-ai-vendor");
  const openBtn = $("btn-open-vendor");
  if (sel && openBtn) {
    sel.onchange = function () {
      const chosen = vendorInfo.vendors.find(function (v) { return v.service === sel.value; });
      if (!chosen) return;
      openBtn.textContent = "🌐 Open " + chosen.name + " & create a key";
      openBtn.dataset.url = chosen.url;
    };
    openBtn.dataset.url = vendor.url;
  }

  const openBtn2 = $("btn-open-vendor");
  if (openBtn2) openBtn2.onclick = function () {
    const url = openBtn2.dataset.url;
    if (!url) return;
    window.open(url, "_blank");
  };
  const pasteKey = $("btn-paste-key");
  if (pasteKey) pasteKey.onclick = async function () {
    const status = $("refresh-ai-status");
    let value = "";
    try {
      value = await navigator.clipboard.readText();
    } catch (e) {
      status.innerHTML = '<span style="color:var(--bad)">clipboard blocked. ' +
        "Press Ctrl+V in the box below instead.</span>" +
        '<input type="text" id="clip-fallback" placeholder="paste here" ' +
        'style="width:100%; margin-top:8px">';
      $("clip-fallback").onkeydown = function (ev) {
        if (ev.key === "Enter") { submit($("clip-fallback").value); }
      };
      return;
    }
    submit(value);
  };

  async function submit(value) {
    const status = $("refresh-ai-status");
    if (!value || !value.trim()) {
      status.innerHTML = '<span style="color:var(--bad)">clipboard is empty - copy the key from the vendor site first</span>';
      return;
    }
    // figure out which vendor the user picked
    const sel = $("refresh-ai-vendor");
    const pickedService = sel ? sel.value : "groq";
    const pickedVendor = (vendorInfo.vendors || []).find(function (v) { return v.service === pickedService; });
    const pickedName = pickedVendor ? pickedVendor.name : pickedService;

    // a soft sanity check: if the value doesn't look like ANY of the
    // known prefixes, warn. We don't refuse - the user knows their key.
    const KNOWN_PREFIXES = ["gsk_", "sk-ant-", "sk-", "sk-proj-", "sk-svcacct-",
                             "hf_", "xai-", "AIza"];
    const cleaned = value.trim();
    if (cleaned.length < 10) {
      status.innerHTML = '<span style="color:var(--bad)">that key is too short to be real. Try again.</span>';
      return;
    }
    if (!KNOWN_PREFIXES.some(function (p) { return cleaned.startsWith(p); })) {
      status.innerHTML = '<span style="color:var(--warn)">warning: this does not start with a known ' +
        'vendor prefix (' + KNOWN_PREFIXES.join(" ") + '). Saving anyway - ' +
        'if it fails the live test, the key will be quarantined.</span>';
    } else {
      status.innerHTML = '<span class="muted small">saving and testing...</span>';
    }
    try {
      const r = await api("/api/keys/add", { service: pickedService, value: cleaned });
      status.innerHTML = '<span style="color:var(--ok)">✓ added ' + esc(r.added) +
        ' for ' + esc(pickedName) + ', alive.</span>';
      refreshRail();
    } catch (e) {
      status.innerHTML = '<span style="color:var(--bad)">' + esc(e.message) + "</span>";
      return;
    }
    // run the pipeline now
    status.innerHTML += '<br><span class="muted small">starting the next video...</span>';
    try {
      await api("/api/run", { what: "video" });
      panel.innerHTML = '<div style="color:var(--ok)">✓ video is rendering. ' +
        'Watch the console (top right of the page) for live output.</div>';
      banner("good", "AI key added - the next video is now rendering");
    } catch (e) {
      status.innerHTML += '<br><span style="color:var(--bad)">could not start: ' +
        esc(e.message) + '</span>';
    }
  }
};

buildSections();
buildRailNav();
refreshRail().then(draw);
</script>
</body>
</html>
"""