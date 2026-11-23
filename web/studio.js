/* Clipsora Studio entry point: routes, shell, first paint. */
import {startRouter, initShell, loadStatus, toast} from "./studio-core.js";
import {renderCreate, renderProcessing, renderProjects, renderProject, renderLibrary} from "./studio-flows.js";
import {renderEditor, renderBrands, renderPublishing, renderAnalytics, renderSettings} from "./studio-workspace.js";

const routes = [
  {match: s => s.length === 0 || s[0] === "create", section: "create", key: () => "create", render: () => renderCreate()},
  {match: s => s[0] === "processing" && !!s[1], section: "projects", key: p => `processing:${p.jid}`,
    params: s => ({jid: s[1]}), render: p => renderProcessing(p)},
  {match: s => s[0] === "projects" && s.length === 1, section: "projects", key: () => "projects", render: () => renderProjects()},
  {match: s => s[0] === "projects" && !!s[1], section: "projects", key: p => `project:${p.jid}`,
    params: s => ({jid: s[1]}), render: p => renderProject(p)},
  {match: s => s[0] === "library" && s.length === 1, section: "library", key: () => "library", render: () => renderLibrary()},
  {match: s => s[0] === "library" && !!s[1] && !!s[2], section: "library", key: p => `clip:${p.jid}:${p.cid}`,
    params: s => ({jid: s[1], cid: s[2]}), render: p => renderEditor(p)},
  {match: s => s[0] === "brands", section: "brands", key: p => `brands:${p.bid || ""}`,
    params: s => ({bid: s[1]}), render: p => renderBrands(p)},
  {match: s => s[0] === "publishing", section: "publishing", key: p => `publishing:${p.jid || ""}:${p.cid || ""}`,
    params: s => ({jid: s[1], cid: s[2]}), render: p => renderPublishing(p)},
  {match: s => s[0] === "analytics", section: "analytics", key: () => "analytics", render: () => renderAnalytics()},
  {match: s => s[0] === "settings", section: "settings", key: () => "settings", render: () => renderSettings()},
];

initShell();
startRouter(routes);

loadStatus().catch(err => {
  console.error(err);
  toast("Could not read the studio status. Some panels may be missing.", "bad");
});

window.addEventListener("unhandledrejection", e => {
  if (e.reason && e.reason.status) e.preventDefault();
});
