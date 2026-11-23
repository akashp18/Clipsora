/* Editor, Brand Kit, Publishing, Analytics, Settings. */
import {
  $, $$, api, state, esc, icon, toast, confirmDialog, pageHead, loading, errorBox, emptyState,
  loadStatus, loadBrands, loadDirections, loadJobs, doneClips, findJob, findClip, coverUrl, fmtDur, when,
  statusBadge, approvalBadge, directionLabel, navigate,
} from "./studio-core.js";
import {optionList, toggleField} from "./studio-flows.js";

const enc = encodeURIComponent;
const PLATFORM_LABEL = {youtube: "YouTube", instagram: "Instagram"};
const CAP_FONT_CSS = {poppins: "Poppins", montserrat: "Montserrat", anton: "Anton", archivo: "'Archivo Black'", playfair: "'Playfair Display'",
  bebas: "'Bebas Neue'", fjalla: "'Fjalla One'", dmserif: "'DM Serif Display'", zilla: "'Zilla Slab SemiBold'",
  bungee: "Bungee", russo: "'Russo One'", marker: "'Permanent Marker'", mono: "'Space Mono'"};
const CAP_FONT_WEIGHT = {poppins: 800, montserrat: 600, anton: 400, archivo: 400, playfair: 400};
const CAP_FONT_LABEL = {
  poppins: "Poppins — geometric display", montserrat: "Montserrat — humanist sans",
  anton: "Anton — condensed display", archivo: "Archivo Black — editorial display",
  playfair: "Playfair Display — cinematic serif", bebas: "Bebas Neue — tall condensed caps",
  fjalla: "Fjalla One — poster condensed", dmserif: "DM Serif Display — high-contrast serif",
  zilla: "Zilla Slab — slab serif", bungee: "Bungee — rounded display caps",
  russo: "Russo One — technical display", marker: "Permanent Marker — handwritten marker",
  mono: "Space Mono — monospace",
};

function capPreset(presets, id) {
  return presets.find(p => p.id === id) || presets[0] || {};
}

function capMerge(clip, presets) {
  const custom = clip.caption_cfg && typeof clip.caption_cfg === "object" ? clip.caption_cfg : {};
  const preset = capPreset(presets, custom.preset || clip.style);
  return {...preset, ...custom, preset: custom.preset || clip.style || preset.id || "bounce"};
}

function capFontStyle(c) {
  return `font-family:${CAP_FONT_CSS[c.font] || "Poppins"};font-weight:${CAP_FONT_WEIGHT[c.font] || 400}`;
}

function capTile(p, selected) {
  const ink = p.base || "#FFFFFF";
  const hit = p.active || "#F0A020";
  const box = p.box && Number(p.box_opacity) > 0 ? p.box : "#16181b";
  const alpha = p.box && Number(p.box_opacity) > 0 ? Math.max(.15, Math.min(1, Number(p.box_opacity) / 100)) : 1;
  const stroke = Number(p.outline) > 0 ? `${Math.max(1, Number(p.outline) * .11)}px ${p.outline_colour || "#000"}` : "0 transparent";
  const shadow = Number(p.shadow) > 0 ? `0 ${Math.max(1, Number(p.shadow) * .25)}px ${Math.max(1, Number(p.shadow) * .6)}px ${p.shadow_colour || "#000"}` : "none";
  const sample = p.transform === "upper" ? "MAKE IT MATTER" : "Make it matter";
  const panel = p.box && Number(p.box_opacity) > 0
    ? `background:linear-gradient(${esc(box)}${Math.round(alpha * 255).toString(16).padStart(2, "0")},${esc(box)}${Math.round(alpha * 255).toString(16).padStart(2, "0")}),#16181b;`
    : "background:#16181b;";
  return `<button type="button" class="cap-tile" data-cap-style="${esc(p.id)}" aria-pressed="${selected ? "true" : "false"}" title="Use ${esc(p.label || p.id)}">
    <span class="cap-tile-art" style="${panel}">
      <span style="${capFontStyle(p)};color:${esc(ink)};font-size:15px;letter-spacing:${Number(p.letter_spacing || 0) * .12}px;-webkit-text-stroke:${stroke};text-shadow:${shadow};text-transform:${p.transform === "upper" ? "uppercase" : "none"}">${sample.split(" ").map((w, i) => `<i style="font-style:normal;color:${i === 2 ? esc(hit) : esc(ink)}">${w}</i>`).join(" ")}</span>
    </span>
    <span class="cap-tile-label">${esc(p.label || p.id)}<em>${esc(p.category || "")}</em></span>
  </button>`;
}

function modal(html) {
  const root = $("#modal-root");
  root.innerHTML = `<div class="modal-back"><div class="modal" role="dialog" aria-modal="true">${html}</div></div>`;
  const close = () => { root.innerHTML = ""; };
  $(".modal-back", root).onclick = e => { if (e.target.classList.contains("modal-back")) close(); };
  return {root, close};
}

function askName({title, label, value = "", ok = "Create"}) {
  return new Promise(resolve => {
    const {root, close} = modal(`<div class="m-body"><h2>${esc(title)}</h2>
      <div class="field"><label for="m-name">${esc(label)}</label><input class="input" id="m-name" value="${esc(value)}"></div>
      <div class="m-actions" style="margin-top:20px"><button class="btn" data-no>Cancel</button><button class="btn primary" data-yes>${esc(ok)}</button></div></div>`);
    const input = $("#m-name", root);
    input.focus(); input.select();
    const done = answer => { close(); resolve(answer); };
    $("[data-no]", root).onclick = () => done(null);
    $("[data-yes]", root).onclick = () => done(input.value.trim() || null);
    input.onkeydown = e => { if (e.key === "Enter") done(input.value.trim() || null); };
  });
}

/* ================================================================ clip editor */
export async function renderEditor({jid, cid}) {
  const [job, status] = await Promise.all([
    api(`/api/jobs/${enc(jid)}`), loadStatus(), loadBrands(),
  ]);
  const clip = findClip(job, cid);
  if (!clip) throw new Error("That clip is no longer part of this project.");

  const [captions, coversData, pub] = await Promise.all([
    api(`/api/jobs/${enc(jid)}/clips/${enc(cid)}/captions`).catch(() => ({words: []})),
    api(`/api/podcast/projects/${enc(jid)}/clips/${enc(cid)}/covers${clip.brand_id ? `?brand_id=${enc(clip.brand_id)}` : ""}`).catch(() => ({candidates: []})),
    api(`/api/publishing/projects/${enc(jid)}/clips/${enc(cid)}`).catch(() => null),
  ]);
  const words = captions.words || [];
  const covers = coversData.candidates || [];
  const captionPresets = status.caption_presets || [];
  const layoutPresets = status.layout_presets || [];
  const initialCap = capMerge(clip, captionPresets);
  const emphasis = (clip.highlight_words || []).join(", ");

  const meta = (label, value) => `<div><div class="tiny faint">${esc(label)}</div><div class="small" style="margin-top:3px">${value}</div></div>`;
  const platforms = pub?.platforms || {};

  const html = `${pageHead({eyebrow: "Clip editor", title: clip.title || clip.hook || "Untitled clip",
    sub: `${fmtDur(clip.end - clip.start)} · ${directionLabel(clip.creative_direction)} · ${job.title || ""}`,
    actions: `<a class="btn" href="#/library">${icon("back")} Library</a>
      ${job.status === "done" ? `<a class="btn" href="/api/podcast/projects/${enc(jid)}/download-approved">${icon("download")} Export package</a>` : ""}
      <button class="btn ${clip.approval_status === "approved" ? "" : "primary"}" id="approve">${icon("check")} ${clip.approval_status === "approved" ? "Approved" : "Approve clip"}</button>`})}

    <div class="editor">
      <div class="preview-col">
        <div class="player">${clip.file && clip.status === "done"
          ? `<div class="player-frame" id="player-frame"><video id="clip-video" controls playsinline preload="metadata" poster="${coverUrl(jid, cid)}" src="${clip.clean_preview ? `/api/jobs/${enc(jid)}/clips/${enc(cid)}/preview` : `/media/${enc(jid)}/${enc(clip.file)}?v=${clip.status}`}"></video>
              <div class="safe-guides" aria-hidden="true"></div><div class="cap-overlay" id="cap-overlay" aria-hidden="true"></div></div>`
          : `<div class="player-empty">${icon("clock")}<div style="margin-top:8px">${clip.status === "done" ? "The file is not ready yet." : "This clip is still being made."}</div></div>`}
          <div class="player-meta"><span>${clip.clean_preview ? "Clean cut · live caption preview" : esc(clip.file || "—")}</span><span>${fmtDur(clip.end - clip.start)}</span></div>
        </div>
        <div class="card card-pad" style="display:grid;grid-template-columns:1fr 1fr;gap:14px">
          ${meta("Approval", approvalBadge(clip.approval_status))}
          ${meta("Status", statusBadge(clip.status))}
          ${meta("Score", `<span class="mono">${Math.round(clip.score || 0)}</span><span class="faint"> / 100</span>`)}
          ${meta("Quality", clip.quality?.ok === false ? `<span class="badge bad">Check</span>` : `<span class="badge ok">Passed</span>`)}
        </div>
        <div class="card card-pad">
          <div class="label">Selected cover</div>
          <div style="margin-top:10px;border-radius:8px;overflow:hidden;border:1px solid var(--line);aspect-ratio:9/16;max-height:260px;width:100%;background:var(--paper-2)">
            <img src="${coverUrl(jid, cid)}?v=${clip.reel_cover || ""}" alt="Cover for this clip" style="width:100%;height:100%;object-fit:cover" onerror="this.style.display='none'">
          </div>
        </div>
      </div>

      <div class="inspector">
        <div class="inner" style="padding-bottom:0">
          <div class="tabs" role="tablist" aria-label="Clip settings">
            <button role="tab" aria-selected="true" data-tab="edit">Edit</button>
            <button role="tab" aria-selected="false" data-tab="captions">Captions <span class="faint">${words.length}</span></button>
            <button role="tab" aria-selected="false" data-tab="covers">Covers <span class="faint">${covers.length}</span></button>
            <button role="tab" aria-selected="false" data-tab="publish">Publishing</button>
          </div>
        </div>
        <div class="inner">
          <section data-panel="edit" class="tab-panel">
            <div class="stack">
              <div class="field"><label for="e-title">Title</label><input class="input" id="e-title" maxlength="100" value="${esc(clip.title || "")}"></div>
              <div class="field"><label for="e-hook">Big text (hook)</label><input class="input" id="e-hook" maxlength="120" value="${esc(clip.hook || "")}">
                <span class="hint">Changing this re-renders the clip so the text on screen matches.</span></div>
              <div class="field"><label for="e-desc">Description</label><textarea class="textarea" id="e-desc" maxlength="2000">${esc(clip.description || "")}</textarea></div>
              <div class="row"><button class="btn primary" id="save-meta">${icon("check")} Save text</button><span class="small muted" id="meta-note"></span></div>
            </div>
            <hr class="hr">
            <div class="form-section">
              <h3>Timing</h3><p>Move the in and out points. The clip is re-cut and re-rendered.</p>
              <div class="timeline">
                <div class="field"><label for="e-start">Start (seconds)</label><input class="input" id="e-start" type="number" step="0.1" min="0" value="${Number(clip.start || 0).toFixed(1)}"></div>
                <div class="field"><label for="e-end">End (seconds)</label><input class="input" id="e-end" type="number" step="0.1" value="${Number(clip.end || 0).toFixed(1)}"></div>
              </div>
              <button class="btn" id="save-times" style="margin-top:12px">${icon("refresh")} Apply timing</button>
            </div>
            <div class="form-section">
              <h3>Look</h3>
              <div class="grid-2">
                <div class="field"><label>Caption style</label><select class="select" id="e-style">${optionList(captionPresets, clip.style)}</select></div>
                <div class="field"><label>Layout</label><select class="select" id="e-layout">${optionList(layoutPresets, clip.layout)}</select></div>
              </div>
              <button class="btn" id="save-look" style="margin-top:12px">${icon("refresh")} Re-render with this look</button>
            </div>
            <div class="form-section">
              <h3>Brand & finish</h3>
              <div class="field"><label for="e-brand">Brand</label><select class="select" id="e-brand">
                <option value="">Keep the current settings</option>${state.brands.map(b => `<option value="${esc(b.id)}"${b.id === clip.brand_id ? " selected" : ""}>${esc(b.name)}</option>`).join("")}
              </select>
                <span class="hint" id="e-brand-hint">${clip.brand_id && !state.brands.some(b => b.id === clip.brand_id)
                  ? "The selected brand no longer exists. This clip uses account branding until you choose another."
                  : "Name, handles, colour, outro, cover and sound come from this brand."}</span></div>
              <div class="stack" style="gap:10px;margin-top:14px">
                ${toggleField("e-captions", "Captions", clip.captions !== false)}
                ${toggleField("e-intro", "Cover intro", !!clip.intro_cover)}
                ${toggleField("e-outro", "Branded outro", clip.outro !== false)}
                ${toggleField("e-watermark", "Watermark", !!clip.watermark)}
                <div id="e-sonic-wrap">${toggleField("e-sonic", "Signature sound", clip.sonic !== false)}</div>
                <div class="row" id="e-sonic-preview" style="gap:10px"></div>
              </div>
              <button class="btn" id="save-finish" style="margin-top:12px">${icon("refresh")} Apply finish</button>
            </div>
            <div class="form-section">
              <h3>Clip actions</h3>
              <div class="row wrap">
                <button class="btn danger sm" id="delete-clip">${icon("trash")} Delete clip</button>
                <a class="btn sm" href="/media/${enc(jid)}/${enc(clip.file || "")}?download=1">${icon("download")} Download this clip</a>
              </div>
            </div>
          </section>

          <section data-panel="captions" class="tab-panel" hidden>
            <div class="row" style="justify-content:space-between;margin-bottom:4px">
              <div><h3 class="section-title">Caption Studio</h3><div class="section-sub">Style, timing, type and emphasis. The preview uses the same style data as the export.</div></div>
              <button class="btn sm" id="retry-captions" title="Ask the AI to tidy the words again">${icon("spark")} Tidy</button>
            </div>
            <div class="cap-gallery" id="cap-gallery" role="group" aria-label="Caption styles">${captionPresets.map(p => capTile(p, p.id === initialCap.preset)).join("")}</div>
            <div class="cap-panel-title">Typography</div>
            <div class="cap-grid">
              <div class="cap-control span"><label for="cap-font">Typeface</label><select class="select" id="cap-font">${optionList(Object.keys(CAP_FONT_CSS).map(id => ({id, label: CAP_FONT_LABEL[id] || id})), initialCap.font)}</select></div>
              <div class="cap-control"><label for="cap-size">Size <output id="cap-size-out">${esc(initialCap.size)}</output></label><input type="range" id="cap-size" min="40" max="220" step="1" value="${esc(initialCap.size)}"></div>
              <div class="cap-control"><label for="cap-letter">Letter spacing <output id="cap-letter-out">${esc(initialCap.letter_spacing)}</output></label><input type="range" id="cap-letter" min="-2" max="20" step="1" value="${esc(initialCap.letter_spacing)}"></div>
              <div class="cap-control"><label for="cap-line">Line height <output id="cap-line-out">${esc(initialCap.line_spacing)}</output></label><input type="range" id="cap-line" min="0.9" max="1.6" step="0.01" value="${esc(initialCap.line_spacing)}"></div>
              <div class="cap-control"><label for="cap-max">Words per group <output id="cap-max-out">${esc(initialCap.max_words)}</output></label><input type="range" id="cap-max" min="1" max="8" step="1" value="${esc(initialCap.max_words)}"></div>
              <div class="cap-control"><label for="cap-transform">Capitalisation</label><select class="select" id="cap-transform">${optionList([{id:"upper",label:"UPPERCASE"},{id:"title",label:"Title case"},{id:"none",label:"As spoken"}], initialCap.transform)}</select></div>
              <div class="cap-control"><label for="cap-position">Position</label><select class="select" id="cap-position">${optionList([{id:"bottom",label:"Bottom, above UI"},{id:"middle",label:"Mid-frame"},{id:"top",label:"Top"}], initialCap.position)}</select></div>
            </div>
            <details class="cap-advanced"><summary>Advanced typography &amp; colour</summary>
              <div class="cap-grid">
                <div class="cap-control"><label for="cap-outline">Stroke <output id="cap-outline-out">${esc(initialCap.outline)}</output></label><input type="range" id="cap-outline" min="0" max="14" step="1" value="${esc(initialCap.outline)}"></div>
                <div class="cap-control"><label for="cap-shadow">Shadow <output id="cap-shadow-out">${esc(initialCap.shadow)}</output></label><input type="range" id="cap-shadow" min="0" max="10" step="1" value="${esc(initialCap.shadow)}"></div>
                <div class="cap-control"><label for="cap-box-opacity">Panel opacity <output id="cap-box-opacity-out">${esc(initialCap.box_opacity)}</output></label><input type="range" id="cap-box-opacity" min="0" max="100" step="1" value="${esc(initialCap.box_opacity)}"></div>
                <div class="cap-control"><label for="cap-highlight">Highlight</label><select class="select" id="cap-highlight">${optionList([{id:"word",label:"Spoken word"},{id:"none",label:"None"}], initialCap.highlight)}</select></div>
                <div class="cap-control span"><label for="cap-box">Panel colour</label><input type="color" class="input" id="cap-box" value="${esc(initialCap.box || "#141612")}"></div>
              </div>
              <div class="cap-grid cap-swatches" style="padding-bottom:12px">
                <label>Text<input type="color" id="cap-base" value="${esc(initialCap.base)}"></label>
                <label>Spoken<input type="color" id="cap-active" value="${esc(initialCap.active)}"></label>
                <label>Emphasis<input type="color" id="cap-strong" value="${esc(initialCap.strong)}"></label>
                <label>Stroke<input type="color" id="cap-outline-colour" value="${esc(initialCap.outline_colour)}"></label>
              </div>
            </details>
            <div class="cap-panel-title">Motion</div>
            <div class="cap-grid">
              <div class="cap-control"><label for="cap-anim">Animation</label><select class="select" id="cap-anim">${optionList(["none","pop","bounce","fade","slide","typewriter","karaoke","scale","glitch"].map(id => ({id, label: id[0].toUpperCase() + id.slice(1)})), initialCap.animation)}</select></div>
              <div class="cap-control"><label for="cap-ms">Duration <output id="cap-ms-out">${esc(initialCap.anim_ms)} ms</output></label><input type="range" id="cap-ms" min="0" max="800" step="10" value="${esc(initialCap.anim_ms)}"></div>
              <div class="cap-control span"><label for="cap-intensity">Intensity <output id="cap-intensity-out">${esc(initialCap.intensity)}</output></label><input type="range" id="cap-intensity" min="0" max="100" step="1" value="${esc(initialCap.intensity)}"></div>
            </div>
            <div class="cap-panel-title">Emphasis</div>
            <div class="cap-control span"><label for="cap-emphasis">Emphasised words <span class="faint">comma-separated, from the transcript</span></label><input class="input" id="cap-emphasis" value="${esc(emphasis)}" placeholder="money, never, actually"></div>
            <div class="cap-actions">
              <button class="btn primary sm" id="save-cap">${icon("check")} Save &amp; render captions</button>
              <button class="btn sm" id="cap-undo" type="button" title="Undo style change">${icon("back")} Undo</button>
              <button class="btn sm" id="cap-redo" type="button" title="Redo style change">Redo</button>
              <button class="btn sm" id="cap-reset" type="button">Reset style</button>
              <label class="toggle small"><input type="checkbox" id="cap-guides"><span class="track"></span><span>Safe guides</span></label>
            </div>
            <hr class="hr">
            <div class="row" style="justify-content:space-between;margin-bottom:10px">
              <div><h3 class="section-title">Transcript &amp; timing</h3><div class="section-sub">Times come from the voice. Edit any word that was heard wrong.</div></div>
            </div>
            <div class="transcript" id="words">${words.length ? words.map((w, i) => `<div class="word-row"><time>${(w.s - clip.start).toFixed(1)}s</time>
              <input value="${esc(w.w)}" data-word="${i}" aria-label="Word ${i + 1}"></div>`).join("") : `<p class="small muted" style="padding:14px">No caption words for this clip.</p>`}</div>
            <div class="row" style="margin-top:12px"><button class="btn primary" id="save-words">${icon("check")} Save captions & re-render</button><span class="small muted" id="words-note"></span></div>
          </section>

          <section data-panel="covers" class="tab-panel" hidden>
            <div class="row" style="justify-content:space-between;margin-bottom:12px">
              <div><h3 class="section-title">The cover</h3><div class="section-sub">${covers.length ? "Ranked from this clip's own frames." : "Make covers from the clip's frames."}</div></div>
              <button class="btn sm" id="gen-covers">${icon("image")} ${covers.length ? "Regenerate" : "Generate covers"}</button>
            </div>
            <div class="cover-options" id="cover-options">${covers.map(c => `<button type="button" class="cover-opt ${c.selected ? "selected" : ""}" data-cover="${esc(c.id)}">
              <img src="/api/podcast/projects/${enc(jid)}/clips/${enc(cid)}/covers/${enc(c.id)}/image?t=${Date.now()}" alt="Cover ${esc(c.headline || "")}" loading="lazy">
              <span class="pick">${c.selected ? "✓" : ""}</span><span class="cl">${esc(c.headline || `${Number(c.time || 0).toFixed(1)}s`)}</span></button>`).join("") ||
              `<div class="auto-note" style="grid-column:1/-1">${icon("info")} No covers yet. ${clip.status === "done" ? "Generate three options from the clip's frames." : "Finish rendering first."}</div>`}</div>
            <div class="row" style="margin-top:14px"><span class="small muted" id="cover-note"></span></div>
          </section>

          <section data-panel="publish" class="tab-panel" hidden>
            <h3 class="section-title">Publishing readiness</h3>
            <div class="section-sub" style="margin-bottom:16px">The packages are prepared per platform. Nothing leaves Clipsora without an explicit approval and a connected account.</div>
            <div class="publish-grid" style="grid-template-columns:1fr 1fr">
              ${["youtube", "instagram"].map(p => {
                const t = platforms[p] || {state: "draft"};
                return `<div class="inset"><div class="row"><strong>${PLATFORM_LABEL[p]}</strong><span class="right state-pill ${esc(t.state)}">${esc(t.state)}</span></div>
                  <div class="small muted" style="margin-top:8px">${t.last_error ? esc(t.last_error) : t.remote_url ? `<a class="link" href="${esc(t.remote_url)}" target="_blank" rel="noopener">Open the post</a>` : "Not prepared yet."}</div>
                  <div class="tiny faint" style="margin-top:10px">${t.attempts || 0} attempt${t.attempts === 1 ? "" : "s"}</div></div>`;
              }).join("")}
            </div>
            <div class="row wrap" style="margin-top:16px">
              <button class="btn primary" id="prepare">${icon("send")} Prepare packages</button>
              <a class="btn" href="#/publishing/${enc(jid)}/${enc(cid)}">${icon("arrow")} Open publishing workspace</a>
            </div>
          </section>
        </div>
      </div>
    </div>`;

  return {
    html, title: clip.title || "Clip editor",
    crumbs: [{label: "Studio", href: "#/create"}, {label: "Library", href: "#/library"}, {label: clip.title || "Clip"}],
    mount(root) {
      $$("[data-tab]", root).forEach(tab => tab.onclick = () => {
        $$("[data-tab]", root).forEach(t => t.setAttribute("aria-selected", String(t === tab)));
        $$("[data-panel]", root).forEach(p => p.hidden = p.dataset.panel !== tab.dataset.tab);
      });

      const busy = async (fn, note) => {
        try { await fn(); } catch (err) { toast(err.message, "bad"); }
      };
      const refresh = async (message) => {
        toast(message || "Queued. The clip will re-render.", "ok");
        state.jobs = null;
        setTimeout(async () => { try { const fresh = await api(`/api/jobs/${enc(jid)}`); const c = findClip(fresh, cid); if (c && c.status === "done") location.reload(); } catch {} }, 2500);
      };

      /* ------------------------------------------------------------ Caption Studio feedback loop */
      let cap = {...initialCap};
      let history = [JSON.stringify(cap)];
      let historyAt = 0;
      let lastGroup = -1;
      const frame = $("#player-frame", root);
      const overlay = $("#cap-overlay", root);
      const video = $("#clip-video", root);
      const capWords = words.map(w => ({...w, s: Number(w.s) - Number(clip.start), e: Number(w.e) - Number(clip.start)}));
      const capSample = ["THIS", "CHANGES", "EVERYTHING"].map((w, i) => ({w, s: i, e: i + 1}));

      const currentEmphasis = () => new Set(String($("#cap-emphasis", root)?.value || "").split(",")
        .map(w => w.trim().toLowerCase().replace(/[^a-z0-9']/g, "")).filter(Boolean));
      const capOut = (id, value) => { const el = $(`#${id}-out`, root); if (el) el.textContent = value; };

      const readControls = () => {
        cap.font = $("#cap-font", root).value;
        cap.size = Number($("#cap-size", root).value);
        cap.letter_spacing = Number($("#cap-letter", root).value);
        cap.line_spacing = Number($("#cap-line", root).value);
        cap.max_words = Number($("#cap-max", root).value);
        cap.transform = $("#cap-transform", root).value;
        cap.position = $("#cap-position", root).value;
        cap.outline = Number($("#cap-outline", root).value);
        cap.shadow = Number($("#cap-shadow", root).value);
        cap.box_opacity = Number($("#cap-box-opacity", root).value);
        cap.highlight = $("#cap-highlight", root).value;
        cap.box = $("#cap-box", root).value;
        cap.base = $("#cap-base", root).value;
        cap.active = $("#cap-active", root).value;
        cap.strong = $("#cap-strong", root).value;
        cap.outline_colour = $("#cap-outline-colour", root).value;
        cap.animation = $("#cap-anim", root).value;
        cap.anim_ms = Number($("#cap-ms", root).value);
        cap.intensity = Number($("#cap-intensity", root).value);
        capOut("cap-size", cap.size); capOut("cap-letter", cap.letter_spacing); capOut("cap-line", cap.line_spacing);
        capOut("cap-max", cap.max_words); capOut("cap-outline", cap.outline); capOut("cap-shadow", cap.shadow);
        capOut("cap-box-opacity", cap.box_opacity); capOut("cap-ms", `${cap.anim_ms} ms`); capOut("cap-intensity", cap.intensity);
      };

      const syncControls = () => {
        $("#cap-font", root).value = cap.font; $("#cap-size", root).value = cap.size;
        $("#cap-letter", root).value = cap.letter_spacing; $("#cap-line", root).value = cap.line_spacing;
        $("#cap-max", root).value = cap.max_words; $("#cap-transform", root).value = cap.transform;
        $("#cap-position", root).value = cap.position; $("#cap-outline", root).value = cap.outline;
        $("#cap-shadow", root).value = cap.shadow; $("#cap-box-opacity", root).value = cap.box_opacity;
        $("#cap-highlight", root).value = cap.highlight; $("#cap-box", root).value = cap.box || "#141612";
        $("#cap-base", root).value = cap.base; $("#cap-active", root).value = cap.active;
        $("#cap-strong", root).value = cap.strong; $("#cap-outline-colour", root).value = cap.outline_colour;
        $("#cap-anim", root).value = cap.animation; $("#cap-ms", root).value = cap.anim_ms;
        $("#cap-intensity", root).value = cap.intensity;
        if ($("#e-style", root)) $("#e-style", root).value = cap.preset;
        $$("[data-cap-style]", root).forEach(b => b.setAttribute("aria-pressed", String(b.dataset.capStyle === cap.preset)));
        readControls();
        renderCaption();
      };

      const remember = () => {
        const next = JSON.stringify(cap);
        if (next === history[historyAt]) return;
        history = history.slice(0, historyAt + 1).concat(next).slice(-40);
        historyAt = history.length - 1;
      };
      const commit = () => { readControls(); remember(); renderCaption(); };

      function capGroups(list, per) {
        const out = []; let clause = [];
        for (const w of list) {
          if (clause.length && (w.s - clause[clause.length - 1].e > .42 || /[.?!]$/.test(clause[clause.length - 1].w))) {
            out.push(...balancedGroups(clause, per)); clause = [];
          }
          clause.push(w);
        }
        if (clause.length) out.push(...balancedGroups(clause, per));
        return out;
      }
      function balancedGroups(seq, per) {
        const count = Math.max(1, Math.ceil(seq.length / Math.max(1, per)));
        const base = Math.floor(seq.length / count), extra = seq.length % count;
        const sizes = Array(count - extra).fill(base).concat(Array(extra).fill(base + 1));
        let at = 0;
        return sizes.map(size => { const chunk = seq.slice(at, at + size); at += size; return chunk; });
      }

      function renderCaption() {
        if (!overlay) return;
        const list = capWords.length ? capWords : capSample;
        const groups = capGroups(list, cap.max_words);
        const now = video ? Number(video.currentTime || 0) : 0;
        let gi = groups.findIndex(g => now >= g[0].s && now <= g[g.length - 1].e + .25);
        if (gi < 0) gi = now < groups[0]?.[0]?.s ? 0 : groups.length - 1;
        const g = groups[gi] || groups[0] || [];
        const activeWord = g.find(w => now >= w.s && now <= w.e) || null;
        const width = Math.max(1, frame?.clientWidth || overlay.clientWidth || 300);
        const scale = width / 1080;
        const family = CAP_FONT_CSS[cap.font] || "Poppins";
        const size = Math.max(9, Number(cap.size) * scale);
        const outline = Math.max(0, Number(cap.outline) * scale * .55);
        const shadow = Number(cap.shadow) > 0 ? `0 ${Math.max(1, Number(cap.shadow) * scale * 1.2)}px ${Math.max(1, Number(cap.shadow) * scale * 2.4)}px ${cap.shadow_colour}` : "none";
        const emphasis = currentEmphasis();
        const box = cap.box && Number(cap.box_opacity) > 0;
        overlay.dataset.pos = cap.position;
        overlay.innerHTML = `<div class="cap-box" style="${box ? `background:${cap.box};opacity:${1};padding:${Math.max(4, size * .28)}px ${Math.max(6, size * .46)}px;border-radius:${Math.max(2, size * .2)}px;` : ""}">
          <div class="cap-line" style="${capFontStyle(cap)};font-size:${size}px;letter-spacing:${Number(cap.letter_spacing) * scale}px;line-height:${cap.line_spacing};gap:0 ${Math.max(2, size * .24)}px">
          ${g.map(w => {
            const text = cap.transform === "upper" ? String(w.w).toUpperCase() : cap.transform === "title" ? String(w.w).replace(/\b\w/g, c => c.toUpperCase()) : String(w.w);
            const hot = activeWord === w && cap.highlight === "word";
            const strong = emphasis.has(String(w.w).toLowerCase().replace(/[^a-z0-9']/g, ""));
            const colour = hot ? cap.active : strong ? cap.strong : cap.base;
            const anim = hot && cap.anim_ms > 0 && ["pop", "bounce", "fade", "slide"].includes(cap.animation) ? cap.animation : "";
            return `<span class="cap-word ${anim}" style="color:${colour};-webkit-text-stroke:${outline}px ${cap.outline_colour};text-shadow:${shadow};--cap-ms:${cap.anim_ms}ms">${esc(text)}</span>`;
          }).join("")}</div></div>`;
        if (box) overlay.querySelector(".cap-box").style.background = `color-mix(in srgb, ${cap.box} ${cap.box_opacity}%, transparent)`;
        lastGroup = gi;
      }

      const bindCap = (id, evt = "input") => { const el = $(`#${id}`, root); if (el) el.addEventListener(evt, commit); };
      ["cap-font","cap-size","cap-letter","cap-line","cap-max","cap-transform","cap-position","cap-outline","cap-shadow","cap-box-opacity","cap-highlight","cap-box","cap-base","cap-active","cap-strong","cap-outline-colour","cap-anim","cap-ms","cap-intensity"].forEach(id => bindCap(id));
      $("#cap-emphasis", root).addEventListener("input", () => { remember(); renderCaption(); });
      $$("[data-cap-style]", root).forEach(tile => tile.onclick = () => {
        const p = capPreset(captionPresets, tile.dataset.capStyle);
        cap = {...p, preset: p.id};
        syncControls(); remember();
      });
      $("#cap-reset", root).onclick = () => { cap = {...capPreset(captionPresets, cap.preset), preset: cap.preset}; syncControls(); remember(); };
      $("#cap-undo", root).onclick = () => { if (historyAt > 0) cap = JSON.parse(history[--historyAt]); syncControls(); };
      $("#cap-redo", root).onclick = () => { if (historyAt < history.length - 1) cap = JSON.parse(history[++historyAt]); syncControls(); };
      $("#cap-guides", root).onchange = e => frame?.classList.toggle("show-guides", e.target.checked);
      if (video) { ["timeupdate", "seeked", "loadedmetadata", "play", "pause"].forEach(evt => video.addEventListener(evt, renderCaption)); }
      if (frame) new ResizeObserver(renderCaption).observe(frame);
      syncControls();

      const saveCaption = async () => {
        readControls();
        const body = {style: cap.preset, layout: $("#e-layout", root).value, caption_cfg: {...cap, preset: cap.preset},
          highlight_words: String($("#cap-emphasis", root).value || "").split(",").map(w => w.trim()).filter(Boolean)};
        await api(`/api/jobs/${enc(jid)}/clips/${enc(cid)}/render`, {method: "POST", body});
        refresh("Captions saved. Rendering with the new style.");
      };
      $("#save-cap", root).onclick = () => busy(saveCaption);

      $("#save-meta", root).onclick = () => busy(async () => {
        const body = {title: $("#e-title", root).value, description: $("#e-desc", root).value};
        const hook = $("#e-hook", root).value;
        if (hook !== (clip.hook || "")) body.hook = hook;
        if (body.hook !== undefined) {
          await api(`/api/jobs/${enc(jid)}/clips/${enc(cid)}/render`, {method: "POST", body: {hook}});
          await api(`/api/podcast/projects/${enc(jid)}/clips/${enc(cid)}/metadata`, {method: "PATCH", body: {title: body.title, description: body.description}});
          await refresh("Text saved. Re-rendering with the new hook.");
        } else {
          await api(`/api/podcast/projects/${enc(jid)}/clips/${enc(cid)}/metadata`, {method: "PATCH", body});
          $("#meta-note", root).textContent = "Saved.";
          toast("Text saved.", "ok");
        }
      });

      $("#save-times", root).onclick = () => busy(async () => {
        const start = Number($("#e-start", root).value), end = Number($("#e-end", root).value);
        if (!(end > start)) throw new Error("The end has to be after the start.");
        await api(`/api/podcast/projects/${enc(jid)}/clips/${enc(cid)}/timestamps`, {method: "PATCH", body: {start, end}});
        refresh("Timing saved. Re-cutting the clip.");
      });

      $("#save-look", root).onclick = () => busy(saveCaption);
      $("#e-style", root).onchange = e => {
        const p = capPreset(captionPresets, e.target.value);
        cap = {...p, preset: p.id}; syncControls(); remember();
      };

      const brandSelect = $("#e-brand", root);
      const showSonic = () => {
        const b = state.brands.find(x => x.id === brandSelect.value);
        const hasSound = Boolean(b?.tokens?.sonic?.asset);
        $("#e-sonic-wrap", root).hidden = !hasSound;
        $("#e-sonic-preview", root).innerHTML = hasSound
          ? `<audio controls preload="none" src="/api/brands/${enc(b.id)}/assets/sonic?t=${Date.now()}" style="height:32px;max-width:240px" aria-label="Preview ${esc(b.name)} signature sound"></audio>`
          : "";
        $("#e-brand-hint", root).textContent = b
          ? `${b.tokens.name}: ${b.tokens.ig_handle ? "@" + b.tokens.ig_handle : "no Instagram handle"}${b.tokens.sonic?.asset ? " · signature sound available" : " · no signature sound"}`
          : "This clip keeps the branding it already has.";
      };
      if (brandSelect) { brandSelect.onchange = showSonic; showSonic(); }

      $("#save-finish", root).onclick = () => busy(async () => {
        const body = {
          captions: $("#e-captions", root).checked,
          intro_cover: $("#e-intro", root).checked,
          outro: $("#e-outro", root).checked,
          watermark: $("#e-watermark", root).checked,
          brand_id: brandSelect ? brandSelect.value : "",
          sonic: $("#e-sonic", root) ? $("#e-sonic", root).checked : true,
        };
        const b = state.brands.find(x => x.id === body.brand_id);
        if (b) Object.assign(body, {brand_name: b.tokens.name, ig_handle: b.tokens.ig_handle, yt_channel: b.tokens.yt_channel, brand_color: b.tokens.accent});
        await api(`/api/jobs/${enc(jid)}/clips/${enc(cid)}/render`, {method: "POST", body});
        refresh("Finish saved. Re-rendering.");
      });

      $("#save-words", root).onclick = () => busy(async () => {
        const edited = $$("[data-word]", root).map((input, i) => ({...words[i], w: input.value.trim()})).filter(w => w.w);
        if (!edited.length) throw new Error("Keep at least one word.");
        await api(`/api/jobs/${enc(jid)}/clips/${enc(cid)}/captions`, {method: "PUT", body: {words: edited}});
        refresh("Captions saved. Re-rendering.");
      });
      $("#retry-captions", root).onclick = () => busy(async () => {
        await api(`/api/jobs/${enc(jid)}/clips/${enc(cid)}/captions`, {method: "PUT", body: {retry: true}});
        refresh("Asking the AI to tidy the words.");
      });

      $("#gen-covers", root).onclick = async e => {
        const btn = e.currentTarget; btn.disabled = true;
        try {
          if (clip.status !== "done") throw new Error("Render the clip first: covers come from its frames.");
          await api(`/api/podcast/projects/${enc(jid)}/clips/${enc(cid)}/covers/generate`, {method: "POST", body: {brand_id: $("#e-brand", root)?.value || ""}});
          toast("Covers generated.", "ok");
          location.reload();
        } catch (err) { toast(err.message, "bad"); btn.disabled = false; }
      };
      $$("[data-cover]", root).forEach(opt => opt.onclick = async () => {
        try {
          await api(`/api/podcast/projects/${enc(jid)}/clips/${enc(cid)}/covers/select`, {method: "POST", body: {cover_id: opt.dataset.cover}});
          $$(".cover-opt", root).forEach(o => { o.classList.toggle("selected", o === opt); $(".pick", o).textContent = o === opt ? "✓" : ""; });
          $("#cover-note", root).textContent = "Selected. The export will use this cover.";
          toast("Cover selected.", "ok");
        } catch (err) { toast(err.message, "bad"); }
      });

      $("#prepare", root).onclick = async e => {
        const btn = e.currentTarget; btn.disabled = true;
        try {
          await api(`/api/publishing/projects/${enc(jid)}/clips/${enc(cid)}/prepare`, {method: "POST", body: {}});
          toast("Packages prepared as drafts. Review them in Publishing.", "ok");
        } catch (err) { toast(err.message, "bad"); btn.disabled = false; }
      };

      $("#approve", root).onclick = async () => {
        const next = clip.approval_status === "approved" ? "recommended" : "approved";
        try {
          await api(`/api/podcast/projects/${enc(jid)}/clips/${enc(cid)}/status`, {method: "PUT", body: {status: next}});
          clip.approval_status = next;
          const b = $("#approve", root);
          b.textContent = next === "approved" ? "Approved" : "Approve clip";
          b.classList.toggle("primary", next !== "approved");
          toast(next === "approved" ? "Clip approved." : "Moved back to review.", "ok");
          state.jobs = null;
        } catch (err) { toast(err.message, "bad"); }
      };

      $("#delete-clip", root).onclick = async () => {
        if (!await confirmDialog({title: "Delete this clip?", text: "The video file and its cover will be removed. This cannot be undone.", ok: "Delete clip", danger: true})) return;
        try { await api(`/api/podcast/projects/${enc(jid)}/clips/${enc(cid)}`, {method: "DELETE"}); state.jobs = null; toast("Clip deleted.", "ok"); navigate("#/library"); }
        catch (err) { toast(err.message, "bad"); }
      };
    },
  };
}

/* ================================================================ brand kit */
export async function renderBrands({bid} = {}) {
  await Promise.all([loadBrands(true), loadStatus(), loadDirections()]);
  const brands = state.brands;
  const chosen = brands.find(b => b.id === bid) || brands[0] || null;
  const t = chosen?.tokens || {};
  const directions = state.directions || [];
  const outroStyles = state.brandMeta.outro_styles || [];
  const typography = [
    {id: "playfair", label: "Playfair Display (editorial serif)"},
    {id: "archivo", label: "Archivo (grotesque)"},
    {id: "poppins", label: "Poppins (geometric)"},
    {id: "inter", label: "Inter (neutral)"},
  ];
  const compositions = [{id: "auto", label: "Auto"}, {id: "editorial", label: "Editorial"}, {id: "statement", label: "Statement"},
    {id: "documentary", label: "Documentary"}, {id: "minimal", label: "Minimal"}, {id: "kinetic", label: "Kinetic"}];

  const editorForm = chosen ? `
    <form id="brand-form" class="card card-pad" style="margin-top:16px">
      <div class="form-section"><h3>Identity</h3><p>The name and handles that appear in end cards and metadata.</p>
        <div class="grid-2">
          <div class="field"><label for="b-name">Brand name</label><input class="input" id="b-name" name="name" maxlength="120" value="${esc(t.name)}" required></div>
          <div class="field"><label for="b-accent">Accent colour</label><div class="row"><input type="color" id="b-accent-pick" value="${esc(t.accent)}" aria-label="Accent colour picker" style="width:44px;height:38px;border:1px solid var(--line);border-radius:6px;background:var(--card)"><input class="input mono" id="b-accent" name="accent" value="${esc(t.accent)}" pattern="#[0-9A-Fa-f]{6}"></div></div>
          <div class="field"><label for="b-ig">Instagram handle</label><input class="input" id="b-ig" name="ig_handle" value="${esc(t.ig_handle)}" placeholder="studio"></div>
          <div class="field"><label for="b-yt">YouTube channel</label><input class="input" id="b-yt" name="yt_channel" value="${esc(t.yt_channel)}" placeholder="studio"></div>
        </div>
        <div class="grid-2" style="margin-top:14px">
          <div class="field"><label for="b-ink">Ink</label><input class="input mono" id="b-ink" name="ink" value="${esc(t.colors?.ink || "#1C1F24")}"></div>
          <div class="field"><label for="b-paper">Paper</label><input class="input mono" id="b-paper" name="paper" value="${esc(t.colors?.paper || "#F5F3EE")}"></div>
        </div>
      </div>

      <div class="form-section"><h3>Voice & type</h3><p>Which direction this brand prefers, and the type it speaks in.</p>
        <div class="grid-2">
          <div class="field"><label for="b-heading">Heading type</label><select class="select" id="b-heading" name="heading">${optionList(typography, t.typography?.heading)}</select></div>
          <div class="field"><label for="b-caption">Caption type</label><select class="select" id="b-caption" name="caption">${optionList(typography, t.typography?.caption)}</select></div>
        </div>
        <div class="row wrap" style="gap:8px;margin-top:14px">
          ${directions.map(d => `<label class="chip"><input type="checkbox" name="direction" value="${esc(d.name || d.id)}"${(t.directions || []).includes(d.name || d.id) ? " checked" : ""}> ${esc(d.label || d.name)}</label>`).join("")}
        </div>
        <p class="hint" style="margin-top:8px">No selection means every direction is allowed.</p>
      </div>

      <div class="form-section"><h3>Covers & outro</h3><p>How covers are composed and how the end card signs off.</p>
        <div class="grid-2">
          <div class="field"><label for="b-comp">Cover composition</label><select class="select" id="b-comp" name="composition">${optionList(compositions, t.cover?.composition)}</select></div>
          <div class="field"><label for="b-outro">Outro style</label><select class="select" id="b-outro" name="outro_style"><option value="auto">Auto by direction</option>${optionList(outroStyles.map(o => ({id: o.id, label: o.label})), t.outro?.style, {})}</select></div>
        </div>
        <div class="field" style="margin-top:14px"><label for="b-tagline">Outro tagline</label><input class="input" id="b-tagline" name="tagline" maxlength="120" value="${esc(t.outro?.tagline || "")}" placeholder="Daily high-signal podcast clips"></div>
        <div class="grid-2" style="margin-top:14px">
          <div class="field"><label for="b-cta-yt">YouTube CTA</label><input class="input" id="b-cta-yt" name="cta_youtube" maxlength="200" value="${esc(t.ctas?.youtube || "")}" placeholder="Subscribe for more conversations."></div>
          <div class="field"><label for="b-cta-ig">Instagram CTA</label><input class="input" id="b-cta-ig" name="cta_instagram" maxlength="200" value="${esc(t.ctas?.instagram || "")}" placeholder="Follow for more."></div>
        </div>
        <div style="margin-top:14px">${toggleField("b-watermark", "Watermark every clip", t.watermark !== false)}</div>
      </div>

      <div class="form-section"><h3>Logo & signature sound</h3> <p>These assets belong to this brand only. The renderer uses this logo and sting when a clip selects ${esc(t.name)}.</p>
        <div class="grid-2">
          <div class="field"><label>Brand logo</label>
            <div class="row" style="gap:12px;align-items:center;margin-top:6px">
              <div class="logo-box" style="width:64px;height:64px;flex:none">${t.logo ? `<img src="/api/brands/${enc(chosen.id)}/assets/logo?t=${Date.now()}" alt="${esc(t.name)} logo">` : icon("image")}</div>
              <div class="stack" style="gap:6px"><button class="btn sm" type="button" id="b-logo-pick">${icon("upload")} ${t.logo ? "Replace" : "Upload"}</button>
                ${t.logo ? `<button class="btn sm ghost" type="button" id="b-logo-remove">Remove</button>` : ""}</div>
            </div>
            <input type="file" id="b-logo-input" accept="image/png,image/jpeg,image/webp" hidden>
            <span class="hint">PNG, JPG or WebP, under 2 MB.</span>
          </div>
          <div class="field"><label>Signature sound</label>
            ${t.sonic?.asset ? `<audio controls preload="none" src="/api/brands/${enc(chosen.id)}/assets/sonic?t=${Date.now()}" style="height:34px;margin:6px 0;max-width:100%" aria-label="${esc(t.name)} signature sound"></audio>` : `<div class="hint" style="margin:8px 0">No sound uploaded for this brand.</div>`}
            <div class="row" style="gap:8px"><button class="btn sm" type="button" id="b-sonic-pick">${icon("upload")} ${t.sonic?.asset ? "Replace sound" : "Upload sound"}</button>
              ${t.sonic?.asset ? `<button class="btn sm ghost" type="button" id="b-sonic-remove">Remove</button>` : ""}</div>
            <input type="file" id="b-sonic-input" accept="audio/mpeg,audio/wav,audio/mp4,audio/aac,audio/ogg,audio/flac" hidden>
            <span class="hint">MP3, WAV, M4A, AAC, OGG or FLAC, 10 seconds or less, under 5 MB.</span>
          </div>
        </div>
      </div>

      <div class="form-section"><h3>Sound</h3><p>A short signature sting under the first second. The renderer lowers it under speech and limits the peak.</p>
        <div class="grid-3">
          <div class="field"><label for="b-gain">Gain (dB)</label><input class="input" id="b-gain" type="number" min="-24" max="6" step="0.5" value="${Number(t.sonic?.gain_db ?? -3)}"></div>
          <div class="field"><label for="b-duck">Duck under speech (dB)</label><input class="input" id="b-duck" type="number" min="-30" max="0" step="0.5" value="${Number(t.sonic?.duck_db ?? -9)}"></div>
          <div class="field"><label for="b-lufs">Target loudness (LUFS)</label><input class="input" id="b-lufs" type="number" min="-24" max="-9" step="0.5" value="${Number(t.sonic?.target_lufs ?? -14)}"></div>
        </div>
        <p class="hint" style="margin-top:10px">${t.sonic?.asset ? "A signature sound is uploaded above. These levels apply when a clip selects this brand." : "Upload a signature sound above to use these levels. Without one, the clip keeps its own audio."}</p>
      </div>

      <div class="row" style="margin-top:18px">
        <button class="btn primary" type="submit">${icon("check")} Save brand</button>
        <span class="small muted" id="brand-note"></span>
        <button class="btn danger sm right" type="button" id="delete-brand">${icon("trash")} Delete</button>
      </div>
    </form>` : emptyState({iconName: "palette", title: "No brand yet", text: "Create a brand to carry a name, handles, colours and an outro into every clip."});

  return {
    html: `${pageHead({eyebrow: "Brand Kit", title: "One identity, every clip.",
      sub: "Colours, type, voice, outro and calls to action. Clips pick all of it from one record, so six episodes still look like one channel.",
      actions: `<button class="btn primary" id="new-brand">${icon("plus")} New brand</button>`})}

      <div class="brand-layout">
        <div>
          <div class="brand-list" id="brand-list">${brands.map(b => `<button class="brand-item" data-brand="${esc(b.id)}" aria-current="${b.id === chosen?.id}">
            <span class="brand-swatch" style="background:${esc(b.tokens.accent)}">${esc(initials(b.name))}</span>
            <span><strong>${esc(b.name)}</strong><span>${b.is_default ? "Default brand" : "Brand"}</span></span></button>`).join("") ||
            `<div class="card-pad small muted">No brands.</div>`}</div>
          <div class="card card-pad" style="margin-top:16px">
            <div class="label">Account logo</div>
            <div class="logo-drop" style="margin-top:10px">
              <div class="logo-box">${state.status?.brand?.has_logo ? `<img src="/api/brand/logo?t=${Date.now()}" alt="Account logo">` : icon("image")}</div>
              <div class="stack" style="gap:6px"><button class="btn sm" id="logo-pick">${icon("upload")} ${state.status?.brand?.has_logo ? "Replace" : "Upload logo"}</button>
                ${state.status?.brand?.has_logo ? `<button class="btn sm ghost" id="logo-remove">Remove</button>` : ""}</div>
            </div>
            <input type="file" id="logo-input" accept="image/png,image/jpeg,image/webp" hidden>
            <p class="hint" style="margin:8px 0 0">PNG under 2 MB. Used on watermarks, covers and the end card.</p>
          </div>
        </div>

        <div>
          ${chosen ? `<div class="brand-preview" style="margin-bottom:0;background:${esc(t.colors?.ink || "#17191C")};border-color:${esc(t.accent)}">
            <div class="bp-kicker">${esc(t.outro?.style === "auto" ? "Brand identity" : t.outro?.style)}</div>
            <h3>${esc(t.name)}</h3>
            <div class="bp-tag">${esc(t.outro?.tagline || "A name, a voice, a frame.")}</div>
            <div class="bp-bar" style="background:${esc(t.accent)}"></div>
            <div class="bp-handles">
              ${t.ig_handle ? `<span><i class="bp-dot" style="background:${esc(t.accent)}"></i>Instagram · @${esc(t.ig_handle)}</span>` : ""}
              ${t.yt_channel ? `<span><i class="bp-dot" style="background:${esc(t.accent)}"></i>YouTube · @${esc(t.yt_channel)}</span>` : ""}
              <span><i class="bp-dot" style="background:${esc(t.secondary || "#F5F3EE")}"></i>${esc(directions.find(d => (t.directions || []).includes(d.name || d.id))?.label || "All creative directions")}</span>
            </div>
          </div>` : ""}
          ${editorForm}
        </div>
      </div>`,
    title: "Brand Kit",
    crumbs: [{label: "Studio", href: "#/create"}, {label: "Brand Kit"}],
    mount(root) {
      $$("[data-brand]", root).forEach(b => b.onclick = () => navigate(`#/brands/${enc(b.dataset.brand)}`));
      $("#new-brand", root).onclick = async () => {
        const name = await askName({title: "New brand", label: "Brand name", ok: "Create brand"});
        if (!name) return;
        try {
          const out = await api("/api/brands", {method: "POST", body: {name, tokens: {name}}});
          await loadBrands(true); toast("Brand created.", "ok"); navigate(`#/brands/${enc(out.brand.id)}`);
        } catch (err) { toast(err.message, "bad"); }
      };

      const accent = $("#b-accent", root), pick = $("#b-accent-pick", root);
      if (accent && pick) {
        pick.oninput = () => { accent.value = pick.value.toUpperCase(); };
        accent.oninput = () => { if (/^#[0-9a-f]{6}$/i.test(accent.value)) pick.value = accent.value; };
      }

      const form = $("#brand-form", root);
      if (form) form.onsubmit = async e => {
        e.preventDefault();
        const directionsChosen = $$('[name="direction"]:checked', form).map(x => x.value);
        const tokens = {
          name: $("#b-name", form).value.trim(),
          accent: $("#b-accent", form).value.trim(),
          ig_handle: $("#b-ig", form).value.trim(),
          yt_channel: $("#b-yt", form).value.trim(),
          colors: {ink: $("#b-ink", form).value.trim(), paper: $("#b-paper", form).value.trim(), accent: $("#b-accent", form).value.trim()},
          typography: {heading: $("#b-heading", form).value, caption: $("#b-caption", form).value},
          directions: directionsChosen,
          cover: {composition: $("#b-comp", form).value},
          outro: {style: $("#b-outro", form).value, tagline: $("#b-tagline", form).value.trim()},
          ctas: {youtube: $("#b-cta-yt", form).value.trim(), instagram: $("#b-cta-ig", form).value.trim()},
          watermark: $("#b-watermark", form).checked,
          sonic: {gain_db: Number($("#b-gain", form).value), duck_db: Number($("#b-duck", form).value), target_lufs: Number($("#b-lufs", form).value)},
        };
        if (!tokens.name) { toast("Give the brand a name.", "bad"); return; }
        try {
          await api(`/api/brands/${enc(chosen.id)}`, {method: "PUT", body: {tokens}});
          await loadBrands(true); toast("Brand saved.", "ok"); navigate(`#/brands/${enc(chosen.id)}`);
        } catch (err) { toast(err.message, "bad"); }
      };
      const del = $("#delete-brand", root);
      if (del) del.onclick = async () => {
        if (!await confirmDialog({title: `Delete ${chosen.name}?`, text: "Clips keep the look they were rendered with, but new clips will not use this brand.", ok: "Delete brand", danger: true})) return;
        try { await api(`/api/brands/${enc(chosen.id)}`, {method: "DELETE"}); await loadBrands(true); toast("Brand deleted.", "ok"); navigate("#/brands"); }
        catch (err) { toast(err.message, "bad"); }
      };

      const logoInput = $("#logo-input", root), logoPick = $("#logo-pick", root);
      if (logoPick) {
        logoPick.onclick = () => logoInput.click();
        logoInput.onchange = async () => {
          const file = logoInput.files[0]; if (!file) return;
          const form = new FormData(); form.append("file", file);
          try { await api("/api/brand/logo", {method: "POST", form}); toast("Logo saved.", "ok"); location.reload(); }
          catch (err) { toast(err.message, "bad"); }
        };
      }
      const logoRemove = $("#logo-remove", root);
      if (logoRemove) logoRemove.onclick = async () => {
        try { await api("/api/brand/logo", {method: "DELETE"}); toast("Logo removed.", "ok"); location.reload(); }
        catch (err) { toast(err.message, "bad"); }
      };

      const uploadBrandAsset = (kind, input) => {
        const pickBtn = $(`#b-${kind}-pick`, root);
        if (!pickBtn) return;
        pickBtn.onclick = () => input.click();
        input.onchange = async () => {
          const file = input.files[0]; if (!file) return;
          const form = new FormData(); form.append("file", file);
          pickBtn.disabled = true;
          try {
            await api(`/api/brands/${enc(chosen.id)}/assets/${kind}`, {method: "POST", form});
            await loadBrands(true); toast(kind === "logo" ? "Brand logo saved." : "Signature sound saved.", "ok");
            navigate(`#/brands/${enc(chosen.id)}`);
          } catch (err) { toast(err.message, "bad"); pickBtn.disabled = false; }
        };
        const removeBtn = $(`#b-${kind}-remove`, root);
        if (removeBtn) removeBtn.onclick = async () => {
          try {
            await api(`/api/brands/${enc(chosen.id)}/assets/${kind}`, {method: "DELETE"});
            await loadBrands(true); toast(kind === "logo" ? "Brand logo removed." : "Signature sound removed.", "ok");
            navigate(`#/brands/${enc(chosen.id)}`);
          } catch (err) { toast(err.message, "bad"); }
        };
      };
      const brandLogoInput = $("#b-logo-input", root);
      if (brandLogoInput) uploadBrandAsset("logo", brandLogoInput);
      const brandSonicInput = $("#b-sonic-input", root);
      if (brandSonicInput) uploadBrandAsset("sonic", brandSonicInput);
    },
  };
}

function initials(name) { return String(name || "B").trim().split(/\s+/).slice(0, 2).map(w => w[0]).join("").toUpperCase(); }

/* ================================================================ publishing */
export async function renderPublishing({jid, cid} = {}) {
  const [jobs, status] = await Promise.all([loadJobs(true), loadStatus()]);
  const rows = doneClips(jobs);
  if (!rows.length) {
    return {html: `${pageHead({eyebrow: "Publishing", title: "Package it per platform.",
      sub: "YouTube and Instagram get separate titles, captions and calls to action."})}
      ${emptyState({iconName: "send", title: "No finished clips yet", text: "Render a clip and its YouTube and Instagram packages will be prepared here.",
        action: `<a class="btn amber" href="#/create">${icon("plus")} Start a project</a>`})}`,
      title: "Publishing", crumbs: [{label: "Studio", href: "#/create"}, {label: "Publishing"}]};
  }
  const pick = rows.find(r => r.job.id === jid && r.clip.id === cid) || rows.find(r => r.job.id === jid) || rows[0];
  const {job, clip} = pick;
  const states = await api(`/api/publishing/projects/${enc(job.id)}/clips/${enc(clip.id)}`).catch(() => ({platforms: {}}));
  const targets = states.platforms || {};
  const ig = clip.instagram || {}, yt = clip.youtube || {};
  const accounts = (status.accounts && status.accounts.list) || [];
  const connected = accounts.map(a => a.platform);

  const stateLine = p => {
    const t = targets[p] || {state: "draft"};
    return `<div class="inset" style="margin-bottom:12px">
      <div class="row"><strong>${PLATFORM_LABEL[p]}</strong><span class="right state-pill ${esc(t.state)}">${esc(t.state)}</span></div>
      ${t.last_error ? `<div class="small" style="color:var(--red);margin-top:6px">${esc(t.last_error)}</div>` : ""}
      ${t.remote_url ? `<a class="link small" href="${esc(t.remote_url)}" target="_blank" rel="noopener">Open the published post</a>` : ""}
      <div class="tiny faint" style="margin-top:8px">${t.attempts || 0} attempt${t.attempts === 1 ? "" : "s"}${t.published_at ? ` · published ${esc(when(t.published_at))}` : ""}</div>
    </div>`;
  };

  const html = `${pageHead({eyebrow: "Publishing", title: "Two platforms, two packages.",
    sub: "Edits stay with the clip. Nothing is uploaded without an approved target, a connected account and an explicit action.",
    actions: `<a class="btn" href="/api/podcast/projects/${enc(job.id)}/download-approved">${icon("download")} Export approved</a>
      <a class="btn primary" href="#/library/${enc(job.id)}/${enc(clip.id)}">${icon("edit")} Open editor</a>`})}

    <div class="publish-head">
      <select class="select" id="pub-clip" style="max-width:420px" aria-label="Choose a clip">
        ${rows.map(r => `<option value="${esc(r.job.id)}:${esc(r.clip.id)}"${r.job.id === job.id && r.clip.id === clip.id ? " selected" : ""}>${esc(r.clip.title || r.clip.hook || "Untitled")} · ${esc(r.job.title || "")}</option>`).join("")}
      </select>
    </div>

    <div class="publish-grid">
      <div class="card">
        <div class="inner" style="padding-bottom:0">
          <div class="platform-tabs" role="tablist" aria-label="Platform">
            <button role="tab" aria-selected="true" data-platform="youtube">${icon("play")} YouTube Shorts</button>
            <button role="tab" aria-selected="false" data-platform="instagram">${icon("image")} Instagram Reels</button>
          </div>
        </div>
        <div class="inner" id="package-panel"></div>
      </div>

      <div class="stack">
        <div class="card card-pad">
          <h3 class="section-title">Readiness</h3>
          <ul class="checklist" style="margin-top:14px">
            <li class="${clip.status === "done" ? "ok" : "bad"}"><span class="tick">${clip.status === "done" ? "✓" : "!"}</span> Clip rendered</li>
            <li class="${clip.approval_status === "approved" ? "ok" : ""}"><span class="tick">${clip.approval_status === "approved" ? "✓" : "!"}</span> ${clip.approval_status === "approved" ? "Approved" : "Not approved yet"}</li>
            <li class="${(clip.title || clip.hook) ? "ok" : "bad"}"><span class="tick">${(clip.title || clip.hook) ? "✓" : "!"}</span> Title or hook present</li>
            ${["youtube", "instagram"].map(p => `<li class="${(targets[p]?.package && Object.keys(targets[p].package).length) ? "ok" : ""}"><span class="tick">${(targets[p]?.package && Object.keys(targets[p].package).length) ? "✓" : "!"}</span> ${PLATFORM_LABEL[p]} package prepared</li>`).join("")}
            <li class="${connected.length ? "ok" : ""}"><span class="tick">${connected.length ? "✓" : "!"}</span> ${connected.length ? `Connected: ${connected.map(p => PLATFORM_LABEL[p] || p).join(", ")}` : "No platform account connected"}</li>
          </ul>
          <div class="row wrap" style="margin-top:16px">
            <button class="btn primary" id="prep">${icon("send")} Prepare packages</button>
            <a class="btn" href="#/settings">${icon("settings")} Connections</a>
          </div>
        </div>
        <div class="card card-pad">
          <h3 class="section-title">Platform state</h3>
          <div style="margin-top:12px">${stateLine("youtube")}${stateLine("instagram")}</div>
          <p class="hint">A reserved attempt is not a post. Clipsora only marks a target published when the platform confirms it.</p>
          <div class="row wrap" style="margin-top:10px">
            <button class="btn sm" id="reserve">Reserve upload slot</button>
            <button class="btn sm" id="reconcile">Reconcile</button>
          </div>
          <p class="hint" style="margin-top:8px">Automatic uploading still happens in the Classic workspace's connected posting queue. Nothing is sent from here.</p>
        </div>
      </div>
    </div>`;

  const pkgHtml = p => {
    const data = p === "youtube" ? yt : ig;
    const target = targets[p]?.package || {};
    const val = k => target[k] ?? data[k] ?? "";
    return `<div class="stack">
      <div class="row"><div><h3 class="section-title" style="font-size:17px">${PLATFORM_LABEL[p]} package</h3>
        <div class="section-sub">${p === "youtube" ? "Title, description and search terms for Shorts." : "Caption, hook and tags for Reels."}</div></div></div>
      <div class="field"><label for="p-title">Title</label><input class="input" id="p-title" maxlength="100" value="${esc(val("title"))}"></div>
      <div class="field"><label for="p-hook">${p === "youtube" ? "Opening line" : "Hook"}</label><input class="input" id="p-hook" maxlength="150" value="${esc(val("hook"))}"></div>
      <div class="field"><label for="p-caption">${p === "youtube" ? "Description" : "Caption"}</label><textarea class="textarea" id="p-caption" rows="6">${esc(val(p === "youtube" ? "description" : "caption"))}</textarea></div>
      <div class="field"><label for="p-tags">Hashtags</label><input class="input" id="p-tags" value="${esc((val("hashtags") || []).join(" "))}" placeholder="podcast clips business"></div>
      <div class="field"><label for="p-cta">Call to action</label><input class="input" id="p-cta" maxlength="200" value="${esc(val("call_to_action") || val("cta") || "")}"></div>
      <div class="row wrap">
        <button class="btn primary" id="save-pkg" data-platform="${p}">${icon("check")} Save ${PLATFORM_LABEL[p]} package</button>
        <span class="small muted" id="pkg-note"></span>
      </div>
      <div class="meta-preview"><h4>${esc(val("title") || clip.hook || clip.title || "Preview")}</h4>
        <p>${esc((val(p === "youtube" ? "description" : "caption") || "").slice(0, 260))}</p></div>
    </div>`;
  };

  return {
    html, title: "Publishing",
    crumbs: [{label: "Studio", href: "#/create"}, {label: "Publishing"}],
    mount(root) {
      let platform = "youtube";
      const panel = $("#package-panel", root);
      const show = p => {
        platform = p;
        $$("[data-platform]", root).forEach(b => b.setAttribute("aria-selected", String(b.dataset.platform === p)));
        panel.innerHTML = pkgHtml(p);
        $("#save-pkg", panel).onclick = savePackage;
      };
      const collect = p => {
        const raw = $("#p-tags", root).value.trim();
        return {
          title: $("#p-title", root).value.trim(),
          hook: $("#p-hook", root).value.trim(),
          [p === "youtube" ? "description" : "caption"]: $("#p-caption", root).value.trim(),
          hashtags: raw ? raw.split(/[\s,]+/).map(t => t.replace(/^#/, "")).filter(Boolean) : [],
          call_to_action: $("#p-cta", root).value.trim(),
        };
      };
      const savePackage = async e => {
        const p = e.currentTarget.dataset.platform;
        const body = collect(p);
        try {
          await api(`/api/publishing/projects/${enc(job.id)}/clips/${enc(clip.id)}/${p}/package`, {method: "PUT", body});
          await api(`/api/podcast/projects/${enc(job.id)}/clips/${enc(clip.id)}/metadata`, {method: "PATCH", body: {[p]: body}});
          toast(`${PLATFORM_LABEL[p]} package saved.`, "ok");
          $("#pkg-note", root).textContent = "Saved.";
        } catch (err) { toast(err.message, "bad"); }
      };
      $$("[data-platform]", root).forEach(b => b.onclick = () => show(b.dataset.platform));
      show("youtube");

      $("#pub-clip", root).onchange = e => {
        const [j, c] = e.target.value.split(":");
        navigate(`#/publishing/${enc(j)}/${enc(c)}`);
      };
      $("#prep", root).onclick = async e => {
        e.currentTarget.disabled = true;
        try { await api(`/api/publishing/projects/${enc(job.id)}/clips/${enc(clip.id)}/prepare`, {method: "POST", body: {}}); toast("Packages prepared as drafts.", "ok"); location.reload(); }
        catch (err) { toast(err.message, "bad"); e.currentTarget.disabled = false; }
      };
      $("#reserve", root).onclick = async () => {
        if (!await confirmDialog({title: "Reserve an upload slot?", text: "This records a durable attempt for the chosen platform. It does not upload anything; the connected posting queue does that. Continue?", ok: "Reserve"})) return;
        try { await api(`/api/publishing/projects/${enc(job.id)}/clips/${enc(clip.id)}/${platform}/attempt`, {method: "POST"}); toast("Upload slot reserved.", "ok"); location.reload(); }
        catch (err) { toast(err.message, "bad"); }
      };
      $("#reconcile", root).onclick = async () => {
        const found = await confirmDialog({title: "Check the platform first", text: "Only reconcile after looking at the platform. Does the post exist there?", ok: "Yes, it exists", danger: false});
        try {
          await api(`/api/publishing/projects/${enc(job.id)}/clips/${enc(clip.id)}/${platform}/reconcile`, {method: "POST", body: {published: !!found, remote_url: ""}});
          toast(found ? "Marked as published." : "Marked as not published.", "ok"); location.reload();
        } catch (err) { toast(err.message, "bad"); }
      };
    },
  };
}

/* ================================================================ analytics */
export async function renderAnalytics() {
  const [jobs, overview, accounts] = await Promise.all([
    loadJobs(true), api("/api/overview").catch(() => null), api("/api/accounts").catch(() => []),
  ]);
  const clips = jobs.flatMap(j => j.clips || []);
  const done = clips.filter(c => c.status === "done");
  const approved = clips.filter(c => c.approval_status === "approved");
  const failed = jobs.filter(j => j.status === "error");
  const creators = overview?.creators || [];
  const postedTotal = creators.reduce((n, c) => n + (c.posted_total || 0), 0);
  const daily = overview?.daily || [];
  const hasHistory = daily.some(d => (d.clips || 0) > 0 || (d.posted || 0) > 0);
  const maxBar = Math.max(1, ...daily.map(d => Math.max(d.clips || 0, d.posted || 0)));
  const accountList = Array.isArray(accounts) ? accounts : (accounts.accounts || []);
  const hasPerformance = accountList.length > 0 && creators.some(c => c.views > 0);

  const kpi = (label, value, note) => `<div class="kpi"><div class="k-label">${esc(label)}</div><div class="k-value">${value}</div><div class="k-note">${esc(note)}</div></div>`;

  return {
    html: `${pageHead({eyebrow: "Analytics", title: "What actually happened.",
      sub: "Counts come from this account's projects and the posting queue. A dash means the platform has not told us; it never means zero."})}

      <div class="kpi-grid">
        ${kpi("Projects", jobs.length, `${jobs.filter(j => j.status === "done").length} finished`)}
        ${kpi("Clips generated", done.length, `${clips.length} candidates`)}
        ${kpi("Approved", approved.length, "ready to publish")}
        ${kpi("Published", hasPerformance || postedTotal ? postedTotal : "—", accountList.length ? "confirmed by the posting queue" : "connect an account to measure")}
      </div>

      <div class="grid-2" style="align-items:start">
        <div class="card card-pad">
          <div class="row"><div><h2 class="section-title">Last 14 days</h2><div class="section-sub">Clips made and posts confirmed</div></div>
            <div class="legend right"><span><i style="background:var(--graphite-2)"></i>Made</span><span><i style="background:var(--amber)"></i>Posted</span></div></div>
          <div class="chart" role="img" aria-label="Clips made and posted over the last 14 days">
            ${hasHistory ? daily.map(d => `<div class="bar" title="${esc(d.day)}: ${d.clips || 0} made, ${d.posted || 0} posted">
              <span class="posted" style="height:${((d.posted || 0) / maxBar * 100).toFixed(1)}%"></span>
              <span style="height:${((d.clips || 0) / maxBar * 100).toFixed(1)}%"></span></div>`).join("") :
              `              <div class="auto-note" style="align-self:center;width:100%">${icon("info")} No daily history yet. It appears after the first finished project.</div>`}
          </div>
          ${hasHistory ? `<div class="chart-x">${daily.map(d => `<span>${esc(String(d.day).slice(5))}</span>`).join("")}</div>` : ""}
        </div>

        <div class="card card-pad">
          <h2 class="section-title">Processing health</h2>
          <div class="section-sub">Every project on this account</div>
          <div class="stack" style="margin-top:16px">
            <div class="row"><span class="grow">Finished cleanly</span><strong>${jobs.filter(j => j.status === "done").length}</strong></div>
            <div class="row"><span class="grow">Still running</span><strong>${jobs.filter(j => j.status === "running" || j.status === "queued").length}</strong></div>
            <div class="row"><span class="grow">Failed</span><strong style="color:${failed.length ? "var(--red)" : "inherit"}">${failed.length}</strong></div>
            <div class="row"><span class="grow">Average processing time</span><strong class="muted">—</strong></div>
          </div>
          <p class="hint" style="margin-top:14px">Processing time is not stored per project yet, so it is shown as missing rather than guessed.</p>
        </div>
      </div>

      <div class="card" style="margin-top:20px">
        <div class="card-head"><div><h2>Platform performance</h2><div class="section-sub">Only what the connected platforms report</div></div></div>
        <div class="card-body">
          ${hasPerformance ? `<div class="table-wrap" tabindex="0" role="region" aria-label="Platform performance"><table class="table"><thead><tr><th>Creator</th><th>Posted</th><th>Views</th><th>Queued</th><th>Failed</th></tr></thead><tbody>
            ${creators.map(c => `<tr><td>${esc(c.name)}</td><td>${c.posted_total || 0}</td><td>${c.views ?? "—"}</td><td>${c.queued || 0}</td><td>${c.failed || 0}</td></tr>`).join("")}
          </tbody></table></div>` : `<div class="auto-note">${icon("info")} No platform is connected, so views and reach are unavailable. This is missing data, not zero. <a class="link" href="#/settings">Connect an account</a>.</div>`}
        </div>
      </div>

      <div class="card" style="margin-top:20px">
        <div class="card-head"><div><h2>By project</h2><div class="section-sub">The same numbers, per episode</div></div></div>
        <div class="card-body" style="overflow:auto">
          ${jobs.length ? `<div class="table-wrap" tabindex="0" role="region" aria-label="Projects"><table class="table"><thead><tr><th>Project</th><th>Status</th><th>Clips</th><th>Approved</th><th>Created</th><th></th></tr></thead><tbody>
            ${jobs.map(j => `<tr><td><a class="link" href="#/projects/${enc(j.id)}">${esc(j.title || "Untitled")}</a></td>
              <td>${statusBadge(j.status)}</td><td>${(j.clips || []).filter(c => c.status === "done").length}</td>
              <td>${(j.clips || []).filter(c => c.approval_status === "approved").length}</td><td>${esc(when(j.created))}</td>
              <td><a class="icon-btn" href="#/projects/${enc(j.id)}" aria-label="Open project">${icon("arrow")}</a></td></tr>`).join("")}
          </tbody></table></div>` : emptyState({iconName: "chart", title: "Nothing measured yet", text: "Process an episode and real numbers will appear here."})}
        </div>
      </div>`,
    title: "Analytics",
    crumbs: [{label: "Studio", href: "#/create"}, {label: "Analytics"}],
  };
}

/* ================================================================ settings */
export async function renderSettings() {
  const [status, settings, ai, storage, accounts] = await Promise.all([
    loadStatus(true),
    api("/api/settings"),
    api("/api/ai").catch(() => null),
    api("/api/storage").catch(() => null),
    api("/api/accounts").catch(() => []),
  ]);
  const accountList = Array.isArray(accounts) ? accounts : (accounts.accounts || []);
  const providers = ai?.providers || [];

  const html = `${pageHead({eyebrow: "Settings", title: "How the studio behaves.",
    sub: "AI, brand defaults, notifications, storage and connected accounts. Secrets are never shown back to this page."})}
    <div class="settings-layout">
      <nav class="settings-nav" aria-label="Settings sections">
        <button data-panel-btn="general" aria-current="true">General</button>
        <button data-panel-btn="ai">AI</button>
        <button data-panel-btn="notifications">Notifications</button>
        <button data-panel-btn="storage">Storage</button>
        <button data-panel-btn="connections">Connections</button>
        <button data-panel-btn="classic">Advanced</button>
      </nav>
      <div>
        <section data-settings="general">
          <form class="card card-pad" id="general-form">
            <h2 class="section-title">Studio defaults</h2><div class="section-sub">Used when a new project does not choose otherwise.</div>
            <div class="grid-2" style="margin-top:16px">
              <div class="field"><label for="s-brand">Brand name</label><input class="input" id="s-brand" name="brand_name" value="${esc(settings.brand_name || "")}"></div>
              <div class="field"><label for="s-color">Brand colour</label><input class="input mono" id="s-color" name="brand_color" value="${esc(settings.brand_color || "#F47B20")}" pattern="#[0-9A-Fa-f]{6}"></div>
              <div class="field"><label for="s-ig">Instagram handle</label><input class="input" id="s-ig" name="ig_handle" value="${esc(settings.ig_handle || "")}"></div>
              <div class="field"><label for="s-yt">YouTube channel</label><input class="input" id="s-yt" name="yt_channel" value="${esc(settings.yt_channel || "")}"></div>
            </div>
            <div class="field" style="margin-top:14px"><label for="s-tagline">Outro tagline</label><input class="input" id="s-tagline" name="outro_tagline" value="${esc(settings.outro_tagline || "")}"></div>
            <div class="stack" style="gap:10px;margin-top:16px">
              ${toggleField("s-intro", "Cover intro on new clips", !!settings.default_intro_cover)}
              ${toggleField("s-watermark", "Watermark on new clips", !!settings.default_watermark)}
              ${toggleField("s-outro", "Branded outro on new clips", !!settings.default_outro)}
              ${toggleField("s-paused", "Pause the posting queue", !!settings.paused, "Nothing new is posted while paused.")}
            </div>
            <div class="row" style="margin-top:18px"><button class="btn primary" type="submit">${icon("check")} Save defaults</button><span class="small muted" id="gen-note"></span></div>
          </form>
          <div class="card card-pad" style="margin-top:16px">
            <h2 class="section-title">Brand Kit</h2><p class="small muted" style="margin:6px 0 14px">Multi-brand identities, covers, outros, CTAs and sonic branding live in the Brand Kit.</p>
            <a class="btn" href="#/brands">${icon("palette")} Open Brand Kit</a>
          </div>
        </section>

        <section data-settings="ai" hidden>
          <form class="card card-pad" id="ai-form">
            <div class="row"><div class="grow"><h2 class="section-title">AI provider</h2><div class="section-sub">${ai?.ready ? `Ready · ${esc(ai.label)}` : "Not configured"}</div></div>
              <span class="badge ${ai?.has_key ? "ok" : "warn"}">${ai?.has_key ? "Key saved" : "No key"}</span></div>
            <div class="grid-2" style="margin-top:16px">
              <div class="field"><label for="ai-provider">Provider</label><select class="select" id="ai-provider">${optionList(providers, ai?.provider || "gemini")}</select></div>
              <div class="field"><label for="ai-models">Model id</label><input class="input mono" id="ai-models" value="${esc((ai?.models || []).join(", "))}" placeholder="gemini-2.5-flash"><span class="hint">Several models may be separated by commas.</span></div>
            </div>
            <div class="field" style="margin-top:14px"><label for="ai-base">Service address (optional)</label><input class="input mono" id="ai-base" value="${esc(ai?.base_url || "")}" placeholder="Only needed for a custom service"></div>
            <div class="field" style="margin-top:14px"><label for="ai-key">API key</label><input class="input" id="ai-key" type="password" autocomplete="new-password" placeholder="${ai?.has_key ? "Leave blank to keep the saved key" : "Paste the key"}">
              <span class="hint">${ai?.key_hint ? `Saved key ends in ${esc(ai.key_hint)}. ` : ""}The key never leaves the server.</span></div>
            <div class="row wrap" style="margin-top:18px">
              <button class="btn primary" type="submit">${icon("check")} Save AI settings</button>
              <button class="btn" type="button" id="ai-test">Test the connection</button>
              <span class="small muted" id="ai-note"></span>
            </div>
          </form>
        </section>

        <section data-settings="notifications" hidden>
          <form class="card card-pad" id="notify-form">
            <h2 class="section-title">Notifications</h2><div class="section-sub">Where Clipsora says that something needs attention.</div>
            <div class="field" style="margin-top:16px"><label for="n-discord">Discord webhook</label><input class="input mono" id="n-discord" value="" placeholder="${settings.discord_webhook ? "A webhook is saved — leave blank to keep it" : "https://discord.com/api/webhooks/…"}"><span class="hint">Saved webhooks are never shown back to this page.</span></div>
            <div class="grid-2" style="margin-top:14px">
              <div class="field"><label for="n-telegram">Telegram bot token</label><input class="input" id="n-telegram" type="password" autocomplete="new-password" placeholder="${settings.telegram_token ? "Saved" : "Bot token"}"></div>
              <div class="field"><label for="n-chat">Telegram chat</label><input class="input" id="n-chat" value="${esc(settings.telegram_chat || "")}"></div>
            </div>
            <div class="row wrap" style="margin-top:18px"><button class="btn primary" type="submit">${icon("check")} Save notifications</button>
              <button class="btn" type="button" id="alert-test">Send a test</button><span class="small muted" id="n-note"></span></div>
          </form>
        </section>

        <section data-settings="storage" hidden>
          <div class="card card-pad">
            <h2 class="section-title">Where everything is kept</h2>
            <div class="section-sub">${storage?.path ? esc(storage.path) : "Storage information is only available to the server owner."}</div>
            ${storage ? `<div class="grid-3" style="margin-top:16px">
              <div class="inset"><div class="tiny faint">Free space</div><div class="section-title" style="margin-top:4px">${storage.free_gb != null ? `${Number(storage.free_gb).toFixed(1)} GB` : "—"}</div></div>
              <div class="inset"><div class="tiny faint">Used by Clipsora</div><div class="section-title" style="margin-top:4px">${storage.used_gb != null ? `${Number(storage.used_gb).toFixed(1)} GB` : "—"}</div></div>
              <div class="inset"><div class="tiny faint">Folder</div><div class="small mono" style="margin-top:6px;word-break:break-all">${esc(storage.path || "—")}</div></div>
            </div>` : `<div class="auto-note" style="margin-top:16px">${icon("info")} Storage settings are managed on the server. The Classic workspace has the folder picker for the owner.</div>`}
            <a class="btn" href="/classic" style="margin-top:16px">${icon("external")} Open storage tools</a>
          </div>
        </section>

        <section data-settings="connections" hidden>
          <div class="card card-pad">
            <div class="row"><div class="grow"><h2 class="section-title">Connected accounts</h2><div class="section-sub">Required before Clipsora can upload on your behalf.</div></div></div>
            <div class="stack" style="margin-top:16px">
              ${accountList.length ? accountList.map(a => `<div class="inset row"><div class="grow"><strong>${esc(a.label || a.platform)}</strong><div class="small muted">${esc(a.name || a.detail || "")}</div></div>
                <button class="btn sm danger" data-remove-account="${esc(a.id)}">Remove</button></div>`).join("") :
                `<div class="auto-note">${icon("info")} No account is connected. Clips can still be exported and posted by hand.</div>`}
            </div>
            <div class="row wrap" style="margin-top:16px">
              ${["youtube", "instagram", "tiktok"].map(p => status?.connect?.[p]
                ? `<a class="btn" href="/oauth/${p}/start">${icon("link")} Connect ${PLATFORM_LABEL[p] || p}</a>`
                : `<span class="chip static">${PLATFORM_LABEL[p] || p}: setup needed</span>`).join("")}
            </div>
            <p class="hint" style="margin-top:10px">Platform app credentials are configured once by the server owner in the Classic workspace, Settings, Connected apps.</p>
          </div>
        </section>

        <section data-settings="classic" hidden>
          <div class="card card-pad">
            <h2 class="section-title">Advanced tools</h2><div class="section-sub">Everything from the first workspace is still here.</div>
            <div class="grid-2" style="margin-top:16px">
              <a class="inset" href="/classic" style="text-decoration:none"><strong>Classic workspace ${icon("external")}</strong><div class="small muted" style="margin-top:4px">Live recording, creator profiles, Style Learner, posting queue and storage tools.</div></a>
              ${status?.user?.role === "admin" ? `<a class="inset" href="/admin" style="text-decoration:none"><strong>Admin ${icon("shield")}</strong><div class="small muted" style="margin-top:4px">Users, feedback and server overview.</div></a>` : ""}
            </div>
            <hr class="hr">
            <div class="row wrap"><a class="btn" href="/privacy">Privacy</a><a class="btn" href="/terms">Terms</a><a class="btn" href="/logout" hidden></a></div>
          </div>
        </section>
      </div>
    </div>`;

  return {
    html, title: "Settings",
    crumbs: [{label: "Studio", href: "#/create"}, {label: "Settings"}],
    mount(root) {
      $$("[data-panel-btn]", root).forEach(btn => btn.onclick = () => {
        $$("[data-panel-btn]", root).forEach(b => b.setAttribute("aria-current", String(b === btn)));
        $$("[data-settings]", root).forEach(s => s.hidden = s.dataset.settings !== btn.dataset.panelBtn);
      });
      $("#general-form", root).onsubmit = async e => {
        e.preventDefault();
        try {
          await api("/api/settings", {method: "PUT", body: {
            brand_name: $("#s-brand", root).value.trim(), brand_color: $("#s-color", root).value.trim(),
            ig_handle: $("#s-ig", root).value.trim(), yt_channel: $("#s-yt", root).value.trim(),
            outro_tagline: $("#s-tagline", root).value.trim(),
            default_intro_cover: $("#s-intro", root).checked, default_watermark: $("#s-watermark", root).checked,
            default_outro: $("#s-outro", root).checked, paused: $("#s-paused", root).checked,
          }});
          await loadStatus(true); toast("Defaults saved.", "ok"); $("#gen-note", root).textContent = "Saved.";
        } catch (err) { toast(err.message, "bad"); }
      };
      const aiForm = $("#ai-form", root);
      if (aiForm) aiForm.onsubmit = async e => {
        e.preventDefault();
        const key = $("#ai-key", root).value;
        const body = {provider: $("#ai-provider", root).value, models: $("#ai-models", root).value, base_url: $("#ai-base", root).value.trim()};
        if (key.trim()) body.key = key.trim();
        try { await api("/api/ai", {method: "PUT", body}); toast("AI settings saved.", "ok"); location.reload(); }
        catch (err) { toast(err.message, "bad"); }
      };
      const aiTest = $("#ai-test", root);
      if (aiTest) aiTest.onclick = async () => {
        aiTest.disabled = true; $("#ai-note", root).textContent = "Asking the provider…";
        try { const out = await api("/api/ai/test", {method: "POST"}); $("#ai-note", root).textContent = `Answered with ${out.model}.`; toast("The AI answered.", "ok"); }
        catch (err) { $("#ai-note", root).textContent = err.message; toast(err.message, "bad"); }
        finally { aiTest.disabled = false; }
      };
      $("#notify-form", root).onsubmit = async e => {
        e.preventDefault();
        const body = {telegram_chat: $("#n-chat", root).value.trim()};
        if ($("#n-discord", root).value.trim()) body.discord_webhook = $("#n-discord", root).value.trim();
        if ($("#n-telegram", root).value.trim()) body.telegram_token = $("#n-telegram", root).value.trim();
        try { await api("/api/settings", {method: "PUT", body}); toast("Notification settings saved.", "ok"); $("#n-note", root).textContent = "Saved."; }
        catch (err) { toast(err.message, "bad"); }
      };
      const alertTest = $("#alert-test", root);
      if (alertTest) alertTest.onclick = async () => {
        try { await api("/api/alerts/test", {method: "POST"}); toast("Test sent.", "ok"); }
        catch (err) { toast(err.message, "bad"); }
      };
      $$("[data-remove-account]", root).forEach(b => b.onclick = async () => {
        if (!await confirmDialog({title: "Remove this account?", text: "Clipsora will no longer be able to post to it.", ok: "Remove", danger: true})) return;
        try { await api(`/api/accounts/${enc(b.dataset.removeAccount)}`, {method: "DELETE"}); toast("Account removed.", "ok"); location.reload(); }
        catch (err) { toast(err.message, "bad"); }
      });
    },
  };
}
