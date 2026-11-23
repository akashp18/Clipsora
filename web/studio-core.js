/* Clipsora Studio — shell, API client, router and small shared pieces.
   Each screen is a module that returns {html, mount}. No framework, no build step. */

export const $ = (sel, root = document) => root.querySelector(sel);
export const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];

export const state = {
  status: null, brands: [], brandMeta: {platforms: [], outro_styles: []},
  directions: [], jobs: null, jobsAt: 0, projects: null, projectsAt: 0,
  route: null, section: "create",
};

const ICONS = {
  spark: '<path d="M12 3v4M12 17v4M3 12h4M17 12h4M6.3 6.3l2.8 2.8M14.9 14.9l2.8 2.8M17.7 6.3l-2.8 2.8M9.1 14.9l-2.8 2.8"/>',
  plus: '<path d="M12 5v14M5 12h14"/>',
  folder: '<path d="M3.5 6.5h6l2 2.5h9v9.5a1 1 0 0 1-1 1h-15a1 1 0 0 1-1-1V7.5a1 1 0 0 1 1-1Z"/>',
  library: '<rect x="3.5" y="4" width="7" height="16" rx="1"/><rect x="13" y="4" width="7" height="10" rx="1"/><path d="M13 18h7"/>',
  palette: '<path d="M12 3.5a8.5 8.5 0 1 0 0 17c1.3 0 1.8-.8 1.8-1.7 0-1.7 1.2-2.3 2.5-2.3H18a3 3 0 0 0 3-3A8.5 8.5 0 0 0 12 3.5Z"/><circle cx="8" cy="9" r="1"/><circle cx="12" cy="7" r="1"/><circle cx="16" cy="9" r="1"/>',
  send: '<path d="m4 12 16-7-5.5 15-2.5-6.5L4 12Z"/><path d="m12 13.5 3-4"/>',
  chart: '<path d="M4 20V10M10 20V5M16 20v-7M22 20H2"/>',
  settings: '<circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.7 1.7 0 0 0 .3 1.9l.1.1-2.7 2.7-.1-.1a1.7 1.7 0 0 0-1.9-.3 1.7 1.7 0 0 0-1 1.5V21h-3.8v-.2a1.7 1.7 0 0 0-1.1-1.5 1.7 1.7 0 0 0-1.9.3l-.1.1L4.5 17l.1-.1a1.7 1.7 0 0 0 .3-1.9 1.7 1.7 0 0 0-1.5-1H3v-3.8h.4a1.7 1.7 0 0 0 1.5-1.1 1.7 1.7 0 0 0-.3-1.9L4.5 7 7.2 4.3l.1.1a1.7 1.7 0 0 0 1.9.3A1.7 1.7 0 0 0 10.3 3H14v.4a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.9-.3l.1-.1L19.7 7l-.1.1a1.7 1.7 0 0 0-.3 1.9 1.7 1.7 0 0 0 1.5 1h.2v3.8h-.2a1.7 1.7 0 0 0-1.4 1.2Z"/>',
  search: '<circle cx="11" cy="11" r="6.5"/><path d="m16 16 4.5 4.5"/>',
  upload: '<path d="M12 16V4M7.5 8.5 12 4l4.5 4.5"/><path d="M4 15v4a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1v-4"/>',
  link: '<path d="M10.5 13.5a4 4 0 0 0 5.7 0l2.5-2.5a4 4 0 0 0-5.7-5.7L11.7 6.6"/><path d="M13.5 10.5a4 4 0 0 0-5.7 0L5.3 13a4 4 0 0 0 5.7 5.7l1.3-1.3"/>',
  play: '<path d="M8 5.5 19 12 8 18.5v-13Z"/>',
  check: '<path d="m5 12.5 4.5 4.5L19 7"/>',
  close: '<path d="m6 6 12 12M18 6 6 18"/>',
  edit: '<path d="M4 20h4l10.5-10.5a2.1 2.1 0 0 0-3-3L5 17v3Z"/><path d="m14.5 6.5 3 3"/>',
  download: '<path d="M12 4v12M7.5 11.5 12 16l4.5-4.5"/><path d="M4 20h16"/>',
  refresh: '<path d="M20 11a8 8 0 1 0-2.3 6.3"/><path d="M20 5v6h-6"/>',
  trash: '<path d="M4 7h16M9 7V4h6v3M6 7l1 13h10l1-13"/><path d="M10 11v5M14 11v5"/>',
  arrow: '<path d="M5 12h14M13 6l6 6-6 6"/>',
  back: '<path d="M19 12H5M11 6l-6 6 6 6"/>',
  clock: '<circle cx="12" cy="12" r="8.5"/><path d="M12 7.5V12l3 2"/>',
  film: '<rect x="3" y="5" width="18" height="14" rx="1.5"/><path d="M7 5v14M17 5v14M3 9h4M17 9h4M3 15h4M17 15h4"/>',
  info: '<circle cx="12" cy="12" r="8.5"/><path d="M12 11v5M12 8h.01"/>',
  shield: '<path d="m12 3 8 3v6c0 4.5-3.3 7.6-8 9-4.7-1.4-8-4.5-8-9V6l8-3Z"/><path d="m9 12 2 2 4-4"/>',
  grid: '<rect x="4" y="4" width="6.5" height="6.5" rx="1"/><rect x="13.5" y="4" width="6.5" height="6.5" rx="1"/><rect x="4" y="13.5" width="6.5" height="6.5" rx="1"/><rect x="13.5" y="13.5" width="6.5" height="6.5" rx="1"/>',
  external: '<path d="M14 4h6v6M20 4l-9 9"/><path d="M18 14v5a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1h5"/>',
  music: '<path d="M9 18V6l10-2v12"/><circle cx="6.5" cy="18" r="2.5"/><circle cx="16.5" cy="16" r="2.5"/>',
  image: '<rect x="3.5" y="4.5" width="17" height="15" rx="1.5"/><circle cx="8.5" cy="9.5" r="1.5"/><path d="m4 17 5-5 4 4 3-3 4 4"/>',
  more: '<circle cx="5" cy="12" r="1"/><circle cx="12" cy="12" r="1"/><circle cx="19" cy="12" r="1"/>',
};

export function icon(name, cls = "") {
  return `<svg class="${cls}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${ICONS[name] || ICONS.info}</svg>`;
}

export function esc(value) {
  return String(value ?? "").replace(/[&<>"']/g, c => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"}[c]));
}

export async function api(path, {method = "GET", body, form, signal} = {}) {
  const opt = {method, headers: {}, signal};
  if (form) opt.body = form;
  else if (body !== undefined) {
    opt.headers["Content-Type"] = "application/json";
    opt.body = JSON.stringify(body);
  }
  const r = await fetch(path, opt);
  if (r.status === 401) {
    location.href = "/login";
    throw new Error("Please sign in.");
  }
  if (!r.ok) {
    let detail = r.statusText;
    try {
      const data = await r.json();
      if (data && data.detail) detail = data.detail;
    } catch { /* not JSON */ }
    const err = new Error(typeof detail === "string" ? detail : `Request failed (${r.status})`);
    err.status = r.status;
    throw err;
  }
  if (r.status === 204) return null;
  return r.json();
}

export function fmtDur(seconds) {
  const s = Math.max(0, Math.round(Number(seconds) || 0));
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
}
export function fmtClock(seconds) {
  const s = Math.max(0, Math.round(Number(seconds) || 0));
  const h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60);
  return h ? `${h}h ${m}m` : m ? `${m}m ${s % 60}s` : `${s}s`;
}
export function fmtBytes(bytes) {
  const b = Number(bytes) || 0;
  if (b < 1024 * 1024) return `${Math.round(b / 1024)} KB`;
  if (b < 1024 ** 3) return `${(b / 1024 ** 2).toFixed(1)} MB`;
  return `${(b / 1024 ** 3).toFixed(2)} GB`;
}
export function when(ts) {
  if (!ts) return "—";
  const t = Number(ts) * (Number(ts) < 1e12 ? 1000 : 1);
  const diff = (Date.now() - t) / 1000;
  if (diff < 60) return "just now";
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
  if (diff < 86400 * 7) return `${Math.floor(diff / 86400)}d ago`;
  return new Date(t).toLocaleDateString(undefined, {day: "numeric", month: "short"});
}
export function initials(name) {
  return String(name || "S").trim().split(/\s+/).slice(0, 2).map(w => w[0]).join("").toUpperCase() || "S";
}
export function coverUrl(jid, cid) { return `/media/${encodeURIComponent(jid)}/${encodeURIComponent(cid)}_cover.jpg`; }
export function thumbUrl(jid) { return `/media/${encodeURIComponent(jid)}/thumb.jpg`; }

export function statusBadge(status) {
  const map = {
    done: ["ok", "Ready"], running: ["warn", "Processing"], queued: ["info", "Queued"],
    error: ["bad", "Failed"], failed: ["bad", "Failed"], cancelled: ["outline", "Stopped"],
  };
  const [kind, label] = map[status] || ["outline", String(status || "Draft")];
  return `<span class="badge ${kind}"><span class="dot"></span>${esc(label)}</span>`;
}
export function approvalBadge(status) {
  const map = {approved: ["ok", "Approved"], rejected: ["bad", "Rejected"], recommended: ["outline", "To review"]};
  const [kind, label] = map[status] || ["outline", "To review"];
  return `<span class="badge ${kind}">${label}</span>`;
}
export function directionLabel(id) {
  if (!id || id === "off") return "No direction";
  const d = state.directions.find(x => x.name === id || x.id === id);
  return d ? (d.label || d.name) : id.replace(/(^|[-_])(\w)/g, (_, __, c) => " " + c.toUpperCase()).trim();
}

export function pageHead({eyebrow, title, sub, actions = "", className = ""}) {
  return `<header class="page-head ${className}">
    <div><div class="eyebrow">${esc(eyebrow || "Clipsora Studio")}</div><h1>${esc(title)}</h1>${sub ? `<p>${esc(sub)}</p>` : ""}</div>
    ${actions ? `<div class="head-actions">${actions}</div>` : ""}
  </header>`;
}
export function loading(text = "Loading the studio…") {
  return `<div class="loading"><span class="spinner" aria-hidden="true"></span><span>${esc(text)}</span></div>`;
}
export function emptyState({iconName = "spark", title, text, action = ""}) {
  return `<div class="empty"><div class="e-icon">${icon(iconName)}</div><h2>${esc(title)}</h2><p>${esc(text)}</p>${action}</div>`;
}
export function errorBox(err, retry = "") {
  return `<div class="error-box"><strong>That didn’t work.</strong>${esc(err && err.message ? err.message : err)}
    ${retry ? `<div style="margin-top:10px"><button class="btn sm" data-retry>${icon("refresh")} Try again</button></div>` : ""}</div>`;
}

export function toast(message, kind = "") {
  if (!message) return;
  const box = $("#toasts");
  if (!box) return;
  const el = document.createElement("div");
  el.className = `toast ${kind}`;
  el.textContent = message;
  box.append(el);
  setTimeout(() => el.remove(), kind === "bad" ? 6500 : 3400);
}

export function confirmDialog({title, text, ok = "Continue", danger = false}) {
  return new Promise(resolve => {
    const root = $("#modal-root");
    root.innerHTML = `<div class="modal-back"><div class="modal" role="dialog" aria-modal="true" aria-labelledby="m-title">
      <div class="m-body"><h2 id="m-title">${esc(title)}</h2><p>${esc(text)}</p>
      <div class="m-actions"><button class="btn" data-no>Cancel</button>
      <button class="btn ${danger ? "danger" : "primary"}" data-yes>${esc(ok)}</button></div></div></div></div>`;
    const close = answer => { root.innerHTML = ""; document.removeEventListener("keydown", key); resolve(answer); };
    const key = e => { if (e.key === "Escape") close(false); };
    root.querySelector("[data-no]").onclick = () => close(false);
    root.querySelector("[data-yes]").onclick = () => close(true);
    root.querySelector(".modal-back").onclick = e => { if (e.target.classList.contains("modal-back")) close(false); };
    root.querySelector("[data-yes]").focus();
    document.addEventListener("keydown", key);
  });
}

export async function loadStatus(force = false) {
  if (state.status && !force) return state.status;
  state.status = await api("/api/status");
  const s = state.status;
  if (s && s.user) {
    const av = $("#avatar");
    if (av) { av.textContent = initials(s.user.name || s.user.email); av.title = s.user.name || s.user.email || "Signed in"; }
  }
  const rail = $("#rail-status-text"), dot = $("#rail-status .dot");
  if (rail) {
    const noFfmpeg = s && s.no_ffmpeg;
    rail.textContent = noFfmpeg ? "ffmpeg is not available" : s && s.disk_full ? "Storage is full" : "Ready";
    if (dot) dot.className = "dot" + (noFfmpeg || (s && s.disk_full) ? " warn" : "");
  }
  const ai = $("#ai-pill");
  if (ai && s) {
    ai.hidden = false;
    ai.innerHTML = s.ai && s.ai.ready ? `<b>AI ready</b>${s.ai.label ? ` · ${esc(s.ai.label)}` : ""}` : `AI not configured`;
  }
  return s;
}
export async function loadBrands(force = false) {
  if (state.brands.length && !force) return state.brands;
  const data = await api("/api/brands");
  state.brands = data.brands || [];
  state.brandMeta = {platforms: data.platforms || [], outro_styles: data.outro_styles || []};
  return state.brands;
}
export async function loadDirections(force = false) {
  if (state.directions.length && !force) return state.directions;
  const data = await api("/api/creative/directions");
  state.directions = Array.isArray(data.directions) ? data.directions : Object.entries(data.directions || {}).map(([id, d]) => ({id, name: id, ...d}));
  return state.directions;
}
export async function loadJobs(force = false) {
  if (state.jobs && !force && Date.now() - state.jobsAt < 4000) return state.jobs;
  state.jobs = await api("/api/jobs");
  state.jobsAt = Date.now();
  return state.jobs;
}
export async function loadProjects(force = false) {
  if (state.projects && !force && Date.now() - state.projectsAt < 5000) return state.projects;
  const data = await api("/api/podcast/projects");
  state.projects = data.projects || [];
  state.projectsAt = Date.now();
  return state.projects;
}
export function doneClips(jobs = state.jobs || []) {
  const out = [];
  for (const j of jobs) for (const c of j.clips || []) if (c.status === "done" && c.file) out.push({job: j, clip: c});
  return out.sort((a, b) => (b.clip.made_at || b.job.created || 0) - (a.clip.made_at || a.job.created || 0));
}
export function findJob(id) { return (state.jobs || []).find(j => j.id === id); }
export function findClip(job, cid) { return (job && (job.clips || []).find(c => c.id === cid)) || null; }

/* ---------------------------------------------------------------- shell + router */
const NAV = [
  {id: "create", label: "Create", iconName: "plus", href: "#/create"},
  {id: "projects", label: "Projects", iconName: "folder", href: "#/projects"},
  {id: "library", label: "Library", iconName: "library", href: "#/library"},
  {id: "brands", label: "Brand Kit", iconName: "palette", href: "#/brands"},
  {id: "publishing", label: "Publishing", iconName: "send", href: "#/publishing"},
  {id: "analytics", label: "Analytics", iconName: "chart", href: "#/analytics"},
  {id: "settings", label: "Settings", iconName: "settings", href: "#/settings"},
];

let routes = [];
let currentKey = "";

export function navMarkup() {
  return `<div class="nav-label">Workspace</div>` + NAV.slice(0, 3).map(n =>
    `<a href="${n.href}" data-section="${n.id}">${icon(n.iconName)}<span>${n.label}</span></a>`).join("") +
    `<div class="nav-label">Identity & output</div>` + NAV.slice(3).map(n =>
    `<a href="${n.href}" data-section="${n.id}">${icon(n.iconName)}<span>${n.label}</span></a>`).join("");
}

export function markNav(section) {
  state.section = section;
  $$("#nav a").forEach(a => {
    if (a.dataset.section === section) a.setAttribute("aria-current", "page");
    else a.removeAttribute("aria-current");
  });
}

export function setCrumbs(parts) {
  const box = $("#crumbs");
  if (!box) return;
  box.innerHTML = parts.map((p, i) => {
    const last = i === parts.length - 1;
    const label = last ? `<strong>${esc(p.label)}</strong>` : (p.href ? `<a href="${esc(p.href)}">${esc(p.label)}</a>` : `<span>${esc(p.label)}</span>`);
    return label + (last ? "" : `<span class="sep">/</span>`);
  }).join("");
}

export function startRouter(defs) {
  routes = defs;
  window.addEventListener("hashchange", renderRoute);
  renderRoute();
}

export function navigate(hash, replace = false) {
  if (location.hash === hash) return renderRoute();
  if (replace) location.replace(hash);
  else location.hash = hash;
}

function parseHash() {
  const raw = location.hash.replace(/^#\/?/, "");
  const [path] = raw.split("?");
  return path.split("/").filter(Boolean).map(decodeURIComponent);
}

async function renderRoute() {
  const segs = parseHash();
  const route = routes.find(r => r.match(segs));
  if (!route) { location.hash = "#/create"; return; }
  const params = route.params ? route.params(segs) : {};
  const key = route.key ? route.key(params) : segs.join("/");
  currentKey = key;
  const view = $("#view");
  markNav(route.section || segs[0] || "create");
  view.innerHTML = loading();
  view.scrollTop = 0;
  window.scrollTo({top: 0, behavior: "instant"});
  let out;
  try {
    out = await route.render(params);
  } catch (err) {
    if (currentKey !== key) return;
    console.error(err);
    view.innerHTML = `<div style="max-width:720px;margin:60px auto">${errorBox(err, "retry")}</div>`;
    const btn = $("[data-retry]", view);
    if (btn) btn.onclick = renderRoute;
    setCrumbs([{label: route.section ? route.section[0].toUpperCase() + route.section.slice(1) : "Studio"}, {label: "Error"}]);
    return;
  }
  if (currentKey !== key) return;             // a newer navigation won
  view.innerHTML = out.html;
  if (out.mount) {
    try { await out.mount(view); } catch (err) {
      console.error(err);
      view.insertAdjacentHTML("afterbegin", `<div style="margin-bottom:16px">${errorBox(err)}</div>`);
    }
  }
  document.title = `${out.title || "Studio"} · Clipsora`;
  setCrumbs(out.crumbs || [{label: out.title || "Studio"}]);
}

export function initShell() {
  const nav = $("#nav");
  if (nav) nav.innerHTML = navMarkup();
  const toggle = $("#rail-toggle"), rail = $("#rail"), scrim = $("#scrim");
  const setRail = open => {
    rail.classList.toggle("open", open);
    scrim.hidden = !open;
    toggle.setAttribute("aria-expanded", String(open));
  };
  if (toggle) toggle.onclick = () => setRail(!rail.classList.contains("open"));
  if (scrim) scrim.onclick = () => setRail(false);
  document.addEventListener("keydown", e => { if (e.key === "Escape") setRail(false); });
  nav && nav.addEventListener("click", e => { if (e.target.closest("a") && innerWidth <= 960) setRail(false); });
}

export function refreshIcons(root = document) { /* icons are inline; kept for symmetry */ }

export async function copyText(text) {
  try { await navigator.clipboard.writeText(text); toast("Copied.", "ok"); }
  catch { toast("Could not copy. Select the text instead.", "bad"); }
}
