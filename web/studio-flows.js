/* Create → processing → projects → library. */
import {
  $, $$, api, state, esc, icon, toast, confirmDialog, pageHead, loading, errorBox, emptyState,
  loadStatus, loadBrands, loadDirections, loadJobs, loadProjects, doneClips, findJob, findClip,
  coverUrl, thumbUrl, fmtDur, fmtClock, fmtBytes, when, statusBadge, approvalBadge, directionLabel,
  navigate, setCrumbs,
} from "./studio-core.js";

/* ---------------------------------------------------------------- input helpers */
export function optionList(items, value, {placeholder = ""} = {}) {
  return (placeholder ? `<option value="">${esc(placeholder)}</option>` : "") + items.map(item => {
    const id = item.id ?? item.name ?? item;
    const label = item.label ?? item.name ?? item;
    return `<option value="${esc(id)}"${String(id) === String(value) ? " selected" : ""}>${esc(label)}</option>`;
  }).join("");
}

export function toggleField(name, label, checked, hint = "") {
  return `<label class="toggle"><input id="${esc(name)}" type="checkbox" name="${esc(name)}"${checked ? " checked" : ""}><span class="track"></span>
    <span>${esc(label)}${hint ? `<span class="hint" style="display:block">${esc(hint)}</span>` : ""}</span></label>`;
}

function brandOptions(value) {
  return state.brands.map(b => `<option value="${esc(b.id)}"${b.id === value ? " selected" : ""}>${esc(b.name)}</option>`).join("");
}
function brandOf(id) { return state.brands.find(b => b.id === id) || state.brands[0] || null; }

/* ---------------------------------------------------------------- chunked upload */
function uploadInParts(file, options, onProgress) {
  return new Promise((resolve, reject) => {
    (async () => {
      let upid = "";
      try {
        const start = await api("/api/upload/start", {method: "POST", body: {name: file.name, size: file.size, options}});
        upid = start.id;
        const part = start.part;
        let sent = 0;
        for (let n = 0; n < start.parts; n++) {
          const slice = file.slice(n * part, Math.min(file.size, (n + 1) * part));
          await new Promise((ok, bad) => {
            const xhr = new XMLHttpRequest();
            xhr.open("PUT", `/api/upload/${upid}/${n}`);
            xhr.upload.onprogress = e => { if (e.lengthComputable) onProgress((sent + e.loaded) / file.size); };
            xhr.onload = () => xhr.status >= 200 && xhr.status < 300 ? ok() :
              bad(new Error(`Piece ${n + 1} was refused (${xhr.status}). ${xhr.responseText ? JSON.parse(xhr.responseText).detail || "" : ""}`));
            xhr.onerror = () => bad(new Error("The connection dropped while sending the file."));
            xhr.send(slice);
          });
          sent += slice.size;
          onProgress(sent / file.size);
        }
        const job = await api(`/api/upload/${upid}/finish`, {method: "POST"});
        resolve(job);
      } catch (err) {
        if (upid) api(`/api/upload/${upid}`, {method: "DELETE"}).catch(() => {});
        reject(err);
      }
    })();
  });
}

/* ---------------------------------------------------------------- create */
export async function renderCreate() {
  const [status] = await Promise.all([loadStatus(), loadBrands(), loadDirections()]);
  const brand = state.brands[0] || null;
  const captionPresets = (status.caption_presets || []).map(p => ({id: p.id, label: p.label}));
  const layoutPresets = (status.layout_presets || []).map(p => ({id: p.id, label: p.label}));

  const html = `${pageHead({
    eyebrow: "New project", title: "Turn a conversation into clips.",
    sub: "Upload an episode or paste a link. Clipsora reads the story, finds the moments that stand alone, and makes each one a finished vertical edit.",
  })}
  <form id="create-form" class="create-grid" novalidate>
    <div class="stack">
      <section class="card source-card" aria-labelledby="source-title">
        <div class="source-tabs" role="tablist" aria-label="Video source">
          <button type="button" role="tab" aria-selected="true" data-source="upload" id="source-title">Upload a file</button>
          <button type="button" role="tab" aria-selected="false" data-source="link">Paste a link</button>
        </div>
        <div id="source-upload">
          <div class="dropzone" id="dropzone" tabindex="0" role="button" aria-label="Choose a video or drop it here">
            <div class="dz-icon">${icon("upload")}</div>
            <h3>Drop the episode here</h3>
            <p>MP4, MOV, MKV or WEBM · a long episode is sent in pieces</p>
            <span class="btn" aria-hidden="true">${icon("upload")} Choose a file</span>
            <input type="file" id="file-input" accept="video/mp4,video/quicktime,video/x-matroska,video/webm,.mp4,.mov,.mkv,.webm" hidden>
          </div>
        </div>
        <div id="source-link" hidden>
          <div class="url-box stack">
            <div class="field"><label for="url">Video address</label>
              <input class="input" id="url" name="url" type="url" placeholder="https://www.youtube.com/watch?v=…" autocomplete="off" spellcheck="false">
              <span class="hint">YouTube, Twitch and Kick links are supported. The video must be public.</span>
            </div>
            <div id="link-preview"></div>
          </div>
        </div>
        <div id="chosen-file"></div>
      </section>

      <section class="card card-pad" aria-labelledby="what-next">
        <div class="row" style="align-items:flex-start;gap:14px">
          <div style="color:var(--amber-2)">${icon("info")}</div>
          <div><h2 id="what-next" class="section-title">What happens next</h2>
            <p class="small muted" style="margin:6px 0 0">Clipsora transcribes the episode, reads where thoughts begin and end, and only then chooses clips. It never stretches a finished thought to hit a length.</p></div>
        </div>
      </section>
    </div>

    <div class="stack">
      <section class="card setup-card" aria-labelledby="setup-title">
        <div class="card-head"><div><h2 id="setup-title">The setup</h2><div class="section-sub">Everything here has a sensible default.</div></div></div>
        <div class="card-body">
          <div class="setup-group">
            <span class="label">Brand</span>
            ${state.brands.length ? `<select class="select" name="brand" aria-label="Brand">${brandOptions(brand && brand.id)}</select>` :
              `<div class="auto-note">${icon("info")} No brand yet. <a class="link" href="#/brands">Create one</a> to carry a name, handles and an outro into every clip.</div>`}
          </div>

          <div class="setup-group">
            <span class="label">Publish to</span>
            <div class="row wrap" style="gap:8px">
              <label class="chip"><input type="checkbox" name="platform" value="youtube" checked> YouTube</label>
              <label class="chip"><input type="checkbox" name="platform" value="instagram" checked> Instagram</label>
            </div>
            <p class="hint" style="margin:8px 0 0">Both packages are prepared separately. Nothing is posted without you.</p>
          </div>

          <div class="setup-group">
            <span class="label">How many clips</span>
            <div class="seg" role="group" aria-label="Clip count">
              <button type="button" data-count="auto" aria-pressed="true">Auto</button>
              <button type="button" data-count="custom" aria-pressed="false">Choose</button>
            </div>
            <div id="count-custom" class="row" hidden style="margin-top:10px">
              <input class="input" type="number" name="max_clips" min="1" max="20" value="6" style="width:90px" aria-label="Number of clips">
              <span class="small muted">clips, at most</span>
            </div>
          </div>

          <div class="setup-group">
            <span class="label">Clip length</span>
            <div class="seg" role="group" aria-label="Clip length">
              <button type="button" data-duration="content" aria-pressed="true">Story-led</button>
              <button type="button" data-duration="range" aria-pressed="false">Set a range</button>
            </div>
            <div id="duration-range" class="row" hidden style="margin-top:10px">
              <input class="input" type="number" name="min_len" min="8" max="120" value="20" style="width:78px" aria-label="Shortest clip, seconds">
              <span class="muted">to</span>
              <input class="input" type="number" name="max_len" min="10" max="180" value="60" style="width:78px" aria-label="Longest clip, seconds">
              <span class="small muted">seconds</span>
            </div>
            <p class="hint" style="margin:8px 0 0" id="duration-note">Each clip ends where its thought ends.</p>
          </div>

          <div class="setup-group">
            <span class="label">Creative direction</span>
            <select class="select" name="direction" aria-label="Creative direction">
              <option value="auto">Choose for the content</option>
              ${state.directions.map(d => `<option value="${esc(d.name || d.id)}">${esc(d.label || d.name)}</option>`).join("")}
            </select>
          </div>

          <details class="setup-group">
            <summary class="label" style="cursor:pointer">Advanced settings</summary>
            <div class="stack" style="margin-top:12px">
              <div class="field"><label for="style">Caption style</label><select class="select" id="style" name="style">${optionList(captionPresets, "bounce")}</select></div>
              <div class="field"><label for="layout">Frame layout</label><select class="select" id="layout" name="layout">${optionList(layoutPresets, "blur")}</select></div>
              <div class="stack" style="gap:9px">
                ${toggleField("captions", "Captions", true)}
                ${toggleField("intro_cover", "Cover intro", false, "Off starts on the first spoken frame.")}
                ${toggleField("outro", "Branded outro", true)}
                ${toggleField("watermark", "Brand watermark", true)}
              </div>
            </div>
          </details>
        </div>
      </section>
    </div>

    <div class="generate-bar">
      <div class="grow"><div class="small muted" id="create-note">Ready when you are.</div>
        <div class="est" id="create-progress" hidden></div></div>
      <button class="btn amber lg" type="submit" id="generate">${icon("spark")} Generate clips</button>
    </div>
  </form>`;

  return {
    html, title: "Create",
    crumbs: [{label: "Studio", href: "#/create"}, {label: "Create"}],
    mount(root) {
      const form = $("#create-form", root);
      let source = "upload", file = null, countMode = "auto", durationMode = "content";

      const setSource = which => {
        source = which;
        $$("[data-source]", root).forEach(b => b.setAttribute("aria-selected", String(b.dataset.source === which)));
        $("#source-upload", root).hidden = which !== "upload";
        $("#source-link", root).hidden = which !== "link";
      };
      $$("[data-source]", root).forEach(b => b.onclick = () => setSource(b.dataset.source));

      const choose = f => {
        if (!f) return;
        const ok = /\.(mp4|mov|mkv|webm)$/i.test(f.name);
        if (!ok) { toast("Choose an MP4, MOV, MKV or WEBM video.", "bad"); return; }
        file = f;
        $("#chosen-file", root).innerHTML = `<div class="file-card"><div class="fc-icon">${icon("film")}</div>
          <div class="grow"><strong>${esc(f.name)}</strong><span>${fmtBytes(f.size)}</span></div>
          <button type="button" class="btn ghost sm" id="remove-file" aria-label="Remove file">${icon("close")}</button></div>`;
        $("#remove-file", root).onclick = () => { file = null; $("#chosen-file", root).innerHTML = ""; $("#file-input", root).value = ""; };
      };
      const input = $("#file-input", root);
      input.onchange = () => choose(input.files[0]);
      const dz = $("#dropzone", root);
      dz.addEventListener("click", () => input.click());
      ["dragenter", "dragover"].forEach(ev => dz.addEventListener(ev, e => { e.preventDefault(); dz.classList.add("hot"); }));
      ["dragleave", "drop"].forEach(ev => dz.addEventListener(ev, e => { e.preventDefault(); dz.classList.remove("hot"); }));
      dz.addEventListener("drop", e => choose(e.dataTransfer.files[0]));
      dz.addEventListener("keydown", e => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); input.click(); } });

      $$("[data-count]", root).forEach(b => b.onclick = () => {
        countMode = b.dataset.count;
        $$("[data-count]", root).forEach(x => x.setAttribute("aria-pressed", String(x === b)));
        $("#count-custom", root).hidden = countMode !== "custom";
      });
      $$("[data-duration]", root).forEach(b => b.onclick = () => {
        durationMode = b.dataset.duration;
        $$("[data-duration]", root).forEach(x => x.setAttribute("aria-pressed", String(x === b)));
        $("#duration-range", root).hidden = durationMode !== "range";
        $("#duration-note", root).textContent = durationMode === "range" ? "Clips stay inside this range; the story still decides where they begin and end." : "Each clip ends where its thought ends.";
      });

      form.onsubmit = async e => {
        e.preventDefault();
        if (source === "upload" && !file) { toast("Choose a video first.", "bad"); dz.focus(); return; }
        const url = $("#url", root).value.trim();
        if (source === "link" && !/^https?:\/\/\S+$/i.test(url)) { toast("Paste a full video link.", "bad"); $("#url", root).focus(); return; }
        const brandId = $('[name="brand"]', root)?.value || "";
        const chosen = brandOf(brandId);
        const options = {
          mode: "podcast",
          duration_mode: durationMode,
          direction: $('[name="direction"]', root).value,
          max_clips: countMode === "auto" ? 8 : Math.max(1, Math.min(20, Number($('[name="max_clips"]', root).value) || 6)),
          style: $('[name="style"]', root)?.value || "bounce",
          layout: $('[name="layout"]', root)?.value || "blur",
          captions: $('[name="captions"]', root).checked,
          intro_cover: $('[name="intro_cover"]', root).checked,
          outro: $('[name="outro"]', root).checked,
          watermark: $('[name="watermark"]', root).checked,
        };
        if (durationMode === "range") {
          options.min_len = Number($('[name="min_len"]', root).value) || 20;
          options.max_len = Number($('[name="max_len"]', root).value) || 60;
        }
        if (chosen) {
          options.brand_id = chosen.id;
          options.brand_name = chosen.tokens.name;
          options.ig_handle = chosen.tokens.ig_handle;
          options.yt_channel = chosen.tokens.yt_channel;
          options.brand_color = chosen.tokens.accent;
        }
        const btn = $("#generate", root), note = $("#create-note", root), bar = $("#create-progress", root);
        btn.disabled = true;
        note.textContent = source === "upload" ? "Sending the episode…" : "Opening the link…";
        bar.hidden = false;
        bar.textContent = source === "upload" ? "0%" : "This can take a moment.";
        try {
          let job;
          if (source === "upload") {
            job = await uploadInParts(file, options, pct => {
              bar.textContent = `${Math.round(pct * 100)}% sent`;
              note.textContent = pct < 1 ? "Sending the episode…" : "Saving and starting…";
            });
          } else {
            job = await api("/api/jobs", {method: "POST", body: {url, options}});
          }
          state.jobs = null;
          toast("Project created. Clipsora is reading it now.", "ok");
          navigate(`#/processing/${encodeURIComponent(job.id)}`);
        } catch (err) {
          toast(err.message, "bad");
          note.textContent = err.message;
          btn.disabled = false;
          bar.hidden = true;
        }
      };
    },
  };
}

/* ---------------------------------------------------------------- processing */
const PIPELINE = [
  ["Ingestion", /download|audio|upload|probe|getting/i],
  ["Transcription", /transcri|speech|reading the transcript|listening/i],
  ["Narrative analysis", /narrative|boundar|sentence|story/i],
  ["Moment discovery", /moment|finding|analys|scor/i],
  ["Clip selection", /select|clip|choos/i],
  ["Creative direction", /direction|style|typograph/i],
  ["Rendering", /render|encod|cutting|making/i],
  ["Cover generation", /cover|frame/i],
  ["Branding", /brand|outro|watermark/i],
  ["Quality validation", /quality|check|validat/i],
  ["Publishing preparation", /publish|package|metadata/i],
];

export async function renderProcessing({jid}) {
  await loadStatus();
  return {
    html: `<div class="processing" id="proc" aria-live="polite">${loading("Connecting to the project…")}</div>`,
    title: "Processing",
    crumbs: [{label: "Studio", href: "#/create"}, {label: "Processing"}],
    mount(root) {
      let timer = null, stopped = false, misses = 0, lastJob = null;
      const box = $("#proc", root);
      const stop = () => { stopped = true; if (timer) clearTimeout(timer); };
      window.addEventListener("hashchange", stop, {once: true});

      const paint = job => {
        lastJob = job;
        const pct = Math.max(0, Math.min(1, Number(job.progress) || 0));
        const stage = job.stage || (job.status === "queued" ? "Waiting in line" : "Working");
        const error = job.error || "";
        const currentIdx = PIPELINE.findIndex(([, re]) => re.test(stage));
        const done = job.status === "done";
        const rows = PIPELINE.map(([name], i) => {
          const stateCls = done || (currentIdx >= 0 && i < currentIdx) ? "done" : currentIdx === i ? "current" : "";
          const mark = stateCls === "done" ? "✓" : stateCls === "current" ? "●" : i + 1;
          return `<li class="${stateCls}"><span class="marker" aria-hidden="true">${mark}</span>
            <span class="st-name">${esc(name)}</span>
            <span class="st-time">${stateCls === "current" ? "Now" : ""}</span></li>`;
        }).join("");

        box.innerHTML = `
          <div class="proc-head">
            <div class="eyebrow" style="justify-content:center">${done ? "Complete" : job.status === "error" ? "Needs attention" : "In progress"}</div>
            <h1>${esc(job.title || job.source?.name || "Your episode")}</h1>
            <p>${done ? "The clips are ready to review." : esc(stage)}</p>
          </div>
          ${error ? `<div class="error-box" style="margin-bottom:18px"><strong>The project stopped.</strong>${esc(error)}</div>` : ""}
          <div class="proc-bar" role="progressbar" aria-valuemin="0" aria-valuemax="100" aria-valuenow="${Math.round(pct * 100)}"><span style="width:${(pct * 100).toFixed(1)}%"></span></div>
          <div class="proc-meta"><span>${done ? "100%" : `${Math.round(pct * 100)}%`}</span>
            <span>${job.clips?.length ? `${job.clips.length} clips so far` : ""} ${job.duration ? `· ${fmtDur(job.duration)} source` : ""}</span></div>
          <ul class="stage-list">${rows}</ul>
          <div class="row" style="margin-top:22px;justify-content:center">
            ${done ? `<a class="btn primary" href="#/projects/${encodeURIComponent(job.id)}">Review the clips ${icon("arrow")}</a>` : ""}
            ${job.status === "error" ? `<button class="btn" data-retry-job>${icon("refresh")} Try again</button>` : ""}
            <button class="btn ghost" data-refresh>${icon("refresh")} Refresh</button>
            <button class="btn ghost" data-stop>${icon("close")} Remove project</button>
          </div>`;

        $("[data-refresh]", box).onclick = () => poll(true);
        $("[data-stop]", box).onclick = async () => {
          if (!await confirmDialog({title: "Remove this project?", text: "The source and any clips made so far will be deleted. This cannot be undone.", ok: "Remove project", danger: true})) return;
          try { await api(`/api/jobs/${encodeURIComponent(jid)}`, {method: "DELETE"}); state.jobs = null; toast("Project removed.", "ok"); navigate("#/projects"); }
          catch (err) { toast(err.message, "bad"); }
        };
        const retry = $("[data-retry-job]", box);
        if (retry) retry.onclick = async () => {
          try { await api(`/api/jobs/${encodeURIComponent(jid)}`, {method: "DELETE"}); state.jobs = null; navigate("#/create"); }
          catch (err) { toast(err.message, "bad"); }
        };
      };

      const poll = async (force = false) => {
        if (stopped) return;
        if (timer) clearTimeout(timer);
        try {
          const job = await api(`/api/jobs/${encodeURIComponent(jid)}`);
          misses = 0;
          paint(job);
          if (job.status === "done" || job.status === "error") { state.jobs = null; return; }
        } catch (err) {
          misses++;
          if (err.status === 404) { box.innerHTML = emptyState({iconName: "folder", title: "That project is gone", text: "It may have been removed in another tab.", action: `<a class="btn" href="#/projects">All projects</a>`}); return; }
          if (misses > 4) { box.innerHTML = errorBox(err, ""); const b = $("[data-retry]", box); if (b) b.onclick = () => poll(true); return; }
        }
        timer = setTimeout(() => poll(), force ? 0 : 1800);
      };
      poll(true);
    },
  };
}

/* ---------------------------------------------------------------- projects */
export async function renderProjects() {
  await Promise.all([loadProjects(true), loadJobs(true)]);
  return {
    html: `${pageHead({eyebrow: "Projects", title: "Every episode, one shelf.",
      sub: "Sources, progress and what came out of them. Open a project to review its clips.",
      actions: `<a class="btn amber" href="#/create">${icon("plus")} New project</a>`})}
      <div class="toolbar">
        <div class="search">${icon("search")}<input class="input" id="project-search" type="search" placeholder="Search projects" aria-label="Search projects"></div>
        <select class="select" id="project-status" style="max-width:170px" aria-label="Filter by status">
          <option value="">All statuses</option><option value="done">Ready</option><option value="running">Processing</option>
          <option value="queued">Queued</option><option value="error">Failed</option>
        </select>
        <select class="select" id="project-sort" style="max-width:190px" aria-label="Sort projects">
          <option value="new">Newest first</option><option value="old">Oldest first</option>
          <option value="clips">Most clips</option><option value="name">Name</option>
        </select>
      </div>
      <div id="projects-list">${loading()}</div>`,
    title: "Projects",
    crumbs: [{label: "Studio", href: "#/create"}, {label: "Projects"}],
    mount(root) {
      const list = $("#projects-list", root);
      const search = $("#project-search", root), status = $("#project-status", root), sort = $("#project-sort", root);
      const draw = () => {
        const q = search.value.trim().toLowerCase();
        let rows = (state.projects || []).filter(p => {
          const job = findJob(p.id);
          const source = `${p.title} ${p.uploader || ""} ${job?.options?.brand_name || ""}`.toLowerCase();
          return (!q || source.includes(q)) && (!status.value || p.status === status.value);
        });
        const sorter = {
          new: (a, b) => (b.created_at || 0) - (a.created_at || 0),
          old: (a, b) => (a.created_at || 0) - (b.created_at || 0),
          clips: (a, b) => (b.clip_count || 0) - (a.clip_count || 0),
          name: (a, b) => String(a.title).localeCompare(String(b.title)),
        }[sort.value];
        rows.sort(sorter);
        if (!rows.length) {
          list.innerHTML = emptyState({iconName: "folder", title: q || status.value ? "No projects match" : "No projects yet",
            text: q || status.value ? "Try a different search or status." : "Bring in an episode and Clipsora will find the moments worth keeping.",
            action: `<a class="btn amber" href="#/create">${icon("plus")} New project</a>`});
          return;
        }
        list.innerHTML = `<div class="list"><div class="list-head"><span>Source</span><span>Project</span><span>Status</span><span>Clips</span><span>Created</span><span></span></div>
          ${rows.map(p => {
            const job = findJob(p.id);
            const brand = job?.options?.brand_name || (brandOf(job?.options?.brand_id)?.tokens?.name) || "—";
            const thumb = job?.thumb ? `<img src="${thumbUrl(p.id)}" alt="" loading="lazy">` : `<div style="height:100%;display:grid;place-items:center;color:#6e6a62">${icon("film")}</div>`;
            return `<a class="list-row" href="#/projects/${encodeURIComponent(p.id)}">
              <div class="thumb">${thumb}${p.duration ? `<span class="dur">${fmtDur(p.duration)}</span>` : ""}</div>
              <div><h3>${esc(p.title || "Untitled")}</h3><div class="sub">${esc(p.uploader || brand)}</div></div>
              <div class="cell">${statusBadge(p.status)}</div>
              <div class="cell"><strong>${p.done_count || 0}/${p.clip_count || 0}</strong><span>ready</span></div>
              <div class="cell optional">${esc(when(p.created_at))}</div>
              <div class="row-end">${icon("arrow")}</div></a>`;
          }).join("")}</div>`;
      };
      [search, status, sort].forEach(el => el.addEventListener("input", draw));
      draw();
    },
  };
}

export async function renderProject({jid}) {
  await loadJobs(true);
  const [detail, clipsData] = await Promise.all([
    api(`/api/podcast/projects/${encodeURIComponent(jid)}`),
    api(`/api/podcast/projects/${encodeURIComponent(jid)}/clips`),
  ]);
  const job = detail.project;
  const clips = clipsData.clips || [];
  const approved = clips.filter(c => c.approval_status === "approved").length;
  const done = clips.filter(c => c.status === "done").length;
  const sourceThumb = findJob(jid)?.thumb ? `<img src="${thumbUrl(jid)}" alt="" style="width:100%;height:100%;object-fit:cover">` : `<div style="display:grid;place-items:center;height:100%;color:#777">${icon("film")}</div>`;

  return {
    html: `${pageHead({eyebrow: "Project", title: job.title || "Untitled episode",
      sub: [job.uploader, job.duration ? `${fmtDur(job.duration)} source` : "", job.detected_categories?.slice(0, 3).join(" · ")].filter(Boolean).join(" · "),
      actions: `<a class="btn" href="#/projects">${icon("back")} All projects</a>
        ${clips.length ? `<a class="btn" href="#/publishing?job=${encodeURIComponent(jid)}">${icon("send")} Publish</a>` : ""}
        ${clips.length ? `<a class="btn primary" href="/api/podcast/projects/${encodeURIComponent(jid)}/download-approved">${icon("download")} Download approved</a>` : ""}`})}

      <div class="grid-4" style="margin-bottom:22px">
        <div class="kpi"><div class="k-label">Status</div><div style="margin:9px 0 5px">${statusBadge(job.status)}</div><div class="k-note">${esc(job.stage || "")}</div></div>
        <div class="kpi"><div class="k-label">Clips</div><div class="k-value">${done}<span class="faint" style="font-size:18px">/${clips.length}</span></div><div class="k-note">rendered</div></div>
        <div class="kpi"><div class="k-label">Approved</div><div class="k-value">${approved}</div><div class="k-note">ready to publish</div></div>
        <div class="kpi"><div class="k-label">Progress</div><div class="k-value">${Math.round((job.progress || 0) * 100)}%</div><div class="k-note">${esc(job.stage || "—")}</div></div>
      </div>

      ${job.status !== "done" && job.status !== "error" ? `<div class="card card-pad" style="margin-bottom:20px"><div class="row"><div class="grow"><h2 class="section-title">Still working</h2><p class="small muted" style="margin:4px 0 0">${esc(job.stage || "Queued")}</p></div><span class="spinner" aria-hidden="true"></span></div></div>` : ""}
      ${job.error ? errorBox(job.error) : ""}

      ${!clips.length ? emptyState({iconName: "film", title: job.status === "done" ? "No clips came out of this one" : "Clips appear as they finish",
        text: job.status === "done" ? "The transcript may not have held a thought that stands alone. Try another episode." : "You can leave this page; processing continues."}) :
        `<div class="list">${clips.map(c => `<div class="list-row" style="grid-template-columns:106px minmax(0,1fr) 120px 110px 100px 34px">
          <a class="thumb" href="#/library/${encodeURIComponent(jid)}/${encodeURIComponent(c.id)}" aria-label="Open clip">${c.status === "done" ? `<img src="${coverUrl(jid, c.id)}" alt="" loading="lazy" onerror="this.replaceWith(Object.assign(document.createElement('div'),{innerHTML:'${icon("film")}',style:'height:100%;display:grid;place-items:center;color:#777'}))">` : `<div style="height:100%;display:grid;place-items:center;color:#777">${icon("clock")}</div>`}<span class="dur">${fmtDur(c.duration)}</span></a>
          <div><h3><a href="#/library/${encodeURIComponent(jid)}/${encodeURIComponent(c.id)}" style="text-decoration:none">${esc(c.title || c.hook || "Untitled clip")}</a></h3><div class="sub">${esc(c.hook || c.explanation || "")}</div></div>
          <div class="cell">${statusBadge(c.status)}</div>
          <div class="cell"><strong>${Math.round(c.score || 0)}</strong><span>score</span></div>
          <div class="cell">${approvalBadge(c.approval_status)}</div>
          <div class="row-end"><a class="icon-btn" href="#/library/${encodeURIComponent(jid)}/${encodeURIComponent(c.id)}" aria-label="Edit">${icon("edit")}</a></div>
        </div>`).join("")}</div>`}`,
    title: job.title || "Project",
    crumbs: [{label: "Studio", href: "#/create"}, {label: "Projects", href: "#/projects"}, {label: job.title || "Project"}],
    mount(root) {
      const row = root.querySelector(".page-head");
      if (row && job.status === "done") {
        const thumb = document.createElement("div");
        thumb.style.cssText = "width:96px;aspect-ratio:16/9;border-radius:8px;overflow:hidden;background:var(--graphite);margin-left:auto";
        thumb.innerHTML = sourceThumb;
        row.append(thumb);
      }
    },
  };
}

/* ---------------------------------------------------------------- library */
export async function renderLibrary() {
  await loadJobs(true);
  return {
    html: `${pageHead({eyebrow: "Library", title: "The finished shelf.",
      sub: "Every rendered clip, with its cover, direction and approval state. Select clips to approve them together.",
      actions: `<a class="btn amber" href="#/create">${icon("plus")} New project</a>`})}
      <div class="toolbar">
        <div class="search">${icon("search")}<input class="input" id="lib-search" type="search" placeholder="Search clips, hooks, projects" aria-label="Search clips"></div>
        <select class="select" id="lib-brand" style="max-width:170px" aria-label="Filter by brand"><option value="">All brands</option></select>
        <select class="select" id="lib-approval" style="max-width:170px" aria-label="Filter by approval">
          <option value="">Any approval</option><option value="approved">Approved</option><option value="recommended">To review</option><option value="rejected">Rejected</option>
        </select>
        <select class="select" id="lib-sort" style="max-width:170px" aria-label="Sort clips">
          <option value="new">Newest</option><option value="score">Highest score</option><option value="long">Longest</option>
        </select>
      </div>
      <div id="lib-bar"></div>
      <div id="lib-grid">${loading()}</div>`,
    title: "Library",
    crumbs: [{label: "Studio", href: "#/create"}, {label: "Library"}],
    mount(root) {
      const grid = $("#lib-grid", root), bar = $("#lib-bar", root);
      const selected = new Set();
      const brandSel = $("#lib-brand", root);
      const brands = [...new Set(doneClips().map(({job}) => job.options?.brand_name).filter(Boolean))];
      brandSel.innerHTML += brands.map(b => `<option value="${esc(b)}">${esc(b)}</option>`).join("");

      const drawBar = () => {
        if (!selected.size) { bar.innerHTML = ""; return; }
        const jobs = [...new Set([...selected].map(k => k.split(":")[0]))];
        bar.innerHTML = `<div class="selectbar"><strong>${selected.size}</strong><span class="muted">selected</span>
          <span class="grow"></span>
          <button class="btn sm" data-approve>${icon("check")} Approve</button>
          ${jobs.map(id => `<a class="btn sm" href="/api/podcast/projects/${encodeURIComponent(id)}/download-approved">${icon("download")} Download</a>`).join("")}
          <button class="btn sm ghost" data-clear>Clear</button></div>`;
        $("[data-clear]", bar).onclick = () => { selected.clear(); draw(); };
        $("[data-approve]", bar).onclick = async () => {
          const byJob = {};
          [...selected].forEach(k => { const [j, c] = k.split(":"); (byJob[j] ||= []).push(c); });
          let n = 0;
          try {
            for (const [j, ids] of Object.entries(byJob)) {
              const out = await api(`/api/podcast/projects/${encodeURIComponent(j)}/batch-approve`, {method: "POST", body: {clip_ids: ids}});
              n += out.approved_count || ids.length;
            }
            toast(`${n} clip${n === 1 ? "" : "s"} approved.`, "ok");
            state.jobs = null; state.projects = null;
            const fresh = await loadJobs(true);
            paint(fresh);
          } catch (err) { toast(err.message, "bad"); }
        };
      };
      const paint = jobs => {
        const all = doneClips(jobs);
        const q = $("#lib-search", root).value.trim().toLowerCase();
        const brand = brandSel.value, approval = $("#lib-approval", root).value, sort = $("#lib-sort", root).value;
        let rows = all.filter(({job, clip}) => {
          const hay = `${clip.title || ""} ${clip.hook || ""} ${job.title || ""} ${job.uploader || ""} ${job.options?.brand_name || ""}`.toLowerCase();
          return (!q || hay.includes(q)) && (!brand || job.options?.brand_name === brand) && (!approval || clip.approval_status === approval);
        });
        rows.sort((a, b) => sort === "score" ? (b.clip.score || 0) - (a.clip.score || 0)
          : sort === "long" ? (b.clip.end - b.clip.start) - (a.clip.end - a.clip.start)
          : (b.clip.made_at || b.job.created || 0) - (a.clip.made_at || a.job.created || 0));
        if (!rows.length) {
          grid.innerHTML = emptyState({iconName: "library", title: all.length ? "Nothing matches those filters" : "The shelf is empty",
            text: all.length ? "Clear a filter or search for something else." : "Finished clips land here after a project has been processed.",
            action: `<a class="btn amber" href="#/create">${icon("plus")} Start a project</a>`});
          drawBar();
          return;
        }
        grid.innerHTML = `<div class="clip-grid">${rows.map(({job, clip}) => {
          const key = `${job.id}:${clip.id}`;
          const dur = fmtDur(clip.end - clip.start);
          return `<article class="clip-card" data-key="${esc(key)}">
            <a class="cc-cover" href="#/library/${encodeURIComponent(job.id)}/${encodeURIComponent(clip.id)}" aria-label="Open ${esc(clip.title || "clip")}">
              <img src="${coverUrl(job.id, clip.id)}" alt="" loading="lazy" onerror="this.style.display='none';this.nextElementSibling.hidden=false">
              <div class="ph" hidden>${icon("film")}</div><span class="cc-dur">${dur}</span>
            </a>
            <div class="cc-tools"><label class="cc-check" title="Select"><input type="checkbox" data-select="${esc(key)}"${selected.has(key) ? " checked" : ""} aria-label="Select clip"></label>
              ${approvalBadge(clip.approval_status)}</div>
            <div class="cc-body"><h3><a href="#/library/${encodeURIComponent(job.id)}/${encodeURIComponent(clip.id)}" style="text-decoration:none">${esc(clip.title || clip.hook || "Untitled clip")}</a></h3>
              <div class="cc-meta"><span>${esc(directionLabel(clip.creative_direction))}</span><span>·</span><span>${Math.round(clip.score || 0)}</span><span class="right">${esc(job.options?.brand_name || "")}</span></div></div>
          </article>`;
        }).join("")}</div>`;
        $$("[data-select]", grid).forEach(cb => cb.onchange = () => {
          if (cb.checked) selected.add(cb.dataset.select); else selected.delete(cb.dataset.select);
          drawBar();
        });
        drawBar();
      };

      paint(state.jobs || []);
      ["lib-search", "lib-brand", "lib-approval", "lib-sort"].forEach(id => {
        const el = document.getElementById(id);
        el.addEventListener("input", () => paint(state.jobs || []));
      });
    },
  };
}
