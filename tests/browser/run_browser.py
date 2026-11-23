"""Browser, accessibility and visual-regression tests for Clipsora Studio.

    python tests/browser/run_browser.py
    python tests/browser/run_browser.py --update-baselines
    python tests/browser/run_browser.py --headed --only editor

Runs against a temporary data folder and a real server; no AI key and no external service is used.
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).parent))

from fixtures import CID, JID, StudioServer, make_wav  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402

BASELINES = Path(__file__).parent / "baselines"
ARTIFACTS = Path(__file__).parent / "artifacts"
AXE = Path(__file__).parent / "vendor" / "axe.min.js"
VIEWPORTS = {"desktop": {"width": 1440, "height": 900},
             "tablet": {"width": 1024, "height": 768},
             "mobile": {"width": 390, "height": 844}}
SCREENS = [
    ("create", "create", "Turn a conversation into clips."),
    ("projects", "projects", "Every episode, one shelf."),
    ("library", "library", "The finished shelf."),
    ("brands", "brands", "One identity, every clip."),
    ("publishing", f"publishing/{JID}/{CID}", "Two platforms, two packages."),
    ("analytics", "analytics", "What actually happened."),
    ("settings", "settings", "How the studio behaves."),
]


class Suite:
    def __init__(self, update: bool, headed: bool, only: str | None) -> None:
        self.update = update
        self.headed = headed
        self.only = only
        self.checks = 0
        self.failures: list[str] = []
        self.current = ""
        self.console: list[str] = []
        self.axe_findings: list[dict] = []

    def check(self, name: str, ok: bool, detail: str = "") -> bool:
        self.checks += 1
        if not ok:
            self.failures.append(f"{self.current}: {name}" + (f" — {detail}" if detail else ""))
            print(f"  FAIL {name}" + (f"   {detail}" if detail else ""))
        return bool(ok)

    def page_errors(self, page, label: str) -> None:
        self.console = []
        page.on("pageerror", lambda exc: self.console.append(f"pageerror: {exc}"))
        page.on("console", lambda msg: self.console.append(f"console: {msg.text}")
                if msg.type == "error" else None)
        page.on("response", lambda r: self.console.append(f"http {r.status}: {r.url}")
                if r.status >= 500 and "/api/" in r.url else None)
        self.current = label

    def settle(self, page) -> None:
        page.wait_for_function("document.fonts && document.fonts.status === 'loaded'")
        page.evaluate("() => new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)))")

    def overflow(self, page) -> list[str]:
        return page.evaluate("""() => {
          const w = window.innerWidth;
          const bad = [];
          const clipped = el => {
            for (let p = el.parentElement; p && p !== document.body; p = p.parentElement) {
              const ox = getComputedStyle(p).overflowX;
              if (ox === 'hidden' || ox === 'auto' || ox === 'scroll') return true;
            }
            return false;
          };
          for (const el of document.querySelectorAll('#view *')) {
            const r = el.getBoundingClientRect();
            if (r.width > 0 && r.height > 0 && (r.right > w + 1 || r.left < -1) && !clipped(el)) {
              bad.push((el.id || el.className || el.tagName) + ':' + Math.round(r.left) + '-' + Math.round(r.right));
            }
          }
          return bad.slice(0, 6);
        }""")

    def screenshot(self, page, viewport: str, name: str) -> None:
        folder = BASELINES / viewport
        folder.mkdir(parents=True, exist_ok=True)
        target = folder / f"{name}.png"
        actual_dir = ARTIFACTS / "actual"
        actual_dir.mkdir(parents=True, exist_ok=True)
        actual = actual_dir / f"{viewport}-{name}.png"
        page.screenshot(path=str(actual), full_page=True, animations="disabled", caret="hide")
        if not target.exists() or self.update:
            shutil.copyfile(actual, target)
            print(f"  baseline {viewport}/{name}.png")
            return
        from PIL import Image, ImageChops
        a, b = Image.open(target).convert("RGB"), Image.open(actual).convert("RGB")
        if a.size != b.size:
            self.check(f"visual {viewport}/{name}", False, f"size {a.size} -> {b.size}")
            return
        diff = ImageChops.difference(a, b)
        changed = sum(1 for px in diff.getdata() if px != (0, 0, 0))
        ratio = changed / max(1, a.width * a.height)
        if ratio > 0.002:
            diff.save(ARTIFACTS / f"diff-{viewport}-{name}.png")
            self.check(f"visual {viewport}/{name}", False, f"{ratio:.3%} pixels changed")
        else:
            self.check(f"visual {viewport}/{name}", True)

    def toast_contains(self, page, text: str, timeout: int = 10000) -> bool:
        try:
            page.wait_for_function(
                "t => [...document.querySelectorAll('.toast')].some(x => x.innerText.includes(t))",
                arg=text, timeout=timeout)
            return True
        except Exception:
            return False

    def axe(self, page, label: str) -> None:
        page.add_script_tag(path=str(AXE))
        result = page.evaluate("""async () => await axe.run(document, {
          runOnly: {type: 'tag', values: ['wcag2a', 'wcag2aa']},
          resultTypes: ['violations']
        })""")
        for violation in result.get("violations", []):
            nodes = [n.get("target") for n in violation.get("nodes", [])][:5]
            item = {"screen": label, "id": violation.get("id"), "impact": violation.get("impact"),
                    "help": violation.get("help"), "nodes": nodes}
            self.axe_findings.append(item)
            if violation.get("impact") in ("serious", "critical"):
                self.check(f"axe {label}: {violation.get('id')}", False,
                           f"{violation.get('impact')} · {violation.get('help')} · {nodes}")

    def run(self, server: StudioServer) -> int:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=not self.headed)
            for viewport, size in VIEWPORTS.items():
                context = browser.new_context(viewport=size, reduced_motion="reduce", color_scheme="light")
                context.tracing.start(screenshots=True, snapshots=True, sources=False)
                page = context.new_page()
                self.page_errors(page, f"{viewport}/navigation")
                for name, route, heading in SCREENS:
                    if self.only and self.only not in name:
                        continue
                    page.goto(f"{server.base}/app#/{route}", wait_until="networkidle")
                    page.wait_for_selector("#view h1", timeout=15000)
                    page.wait_for_function("h => document.querySelector('#view h1')?.innerText.includes(h)",
                                           arg=heading, timeout=15000)
                    self.settle(page)
                    self.check(f"{name} renders", heading in page.locator("#view h1").inner_text())
                    bad = self.overflow(page)
                    self.check(f"{name} has no horizontal overflow", not bad, str(bad))
                    self.screenshot(page, viewport, name)
                    if viewport == "desktop":
                        self.axe(page, name)
                    if self.console:
                        self.check(f"{name} console clean", False, str(self.console[:4]))
                        self.console = []

                page.goto(f"{server.base}/classic", wait_until="networkidle")
                page.wait_for_selector("body", timeout=15000)
                self.check("classic workspace loads", "Clipsora" in page.content())
                self.screenshot(page, viewport, "classic")
                ARTIFACTS.mkdir(parents=True, exist_ok=True)
                trace = ARTIFACTS / f"trace-{viewport}.zip"
                context.tracing.stop(path=str(trace) if self.failures else None)
                if trace.exists() and not self.failures:
                    trace.unlink()
                context.close()

            context = browser.new_context(viewport=VIEWPORTS["desktop"], reduced_motion="reduce")
            context.tracing.start(screenshots=True, snapshots=True, sources=False)
            page = context.new_page()
            self.page_errors(page, "create")
            if not self.only or "create" in self.only:
                self.create_flow(page, server)
            if not self.only or "library" in self.only:
                self.library_and_editor(page, server)
            if not self.only or "brands" in self.only:
                self.brand_kit(page, server)
            if not self.only or "publishing" in self.only:
                self.publishing(page, server)
            trace = ARTIFACTS / "trace-journeys.zip"
            context.tracing.stop(path=str(trace) if self.failures else None)
            if trace.exists() and not self.failures:
                trace.unlink()
            context.close()
            self.playback(p, server)
            browser.close()
        return 0 if not self.failures else 1

    def playback(self, p, server) -> None:
        """Decode the actual H.264 fixture in a browser engine that ships the codec."""
        self.current = "playback"
        for _ in range(60):
            state = None
            try:
                import urllib.request
                with urllib.request.urlopen(f"{server.base}/api/jobs/{JID}", timeout=3) as resp:
                    state = json.load(resp)
                clip = next(c for c in state.get("clips", []) if c.get("id") == CID)
                if clip.get("status") == "done" and clip.get("file"):
                    break
            except Exception:
                pass
            time.sleep(0.5)
        else:
            detail = "no job state"
            try:
                detail = json.dumps(state)[:500] if state else detail
            except Exception:
                pass
            self.check("the real clip re-render finishes", False, detail)
        browser = p.firefox.launch(headless=True)
        context = browser.new_context(viewport=VIEWPORTS["desktop"], reduced_motion="reduce")
        page = context.new_page()
        self.page_errors(page, "playback")
        page.goto(f"{server.base}/app#/library/{JID}/{CID}", wait_until="networkidle")
        page.wait_for_selector("#clip-video", timeout=15000)
        try:
            page.wait_for_function("() => document.querySelector('#clip-video').readyState >= 1", timeout=20000)
            duration = page.locator("#clip-video").evaluate("v => v.duration")
            page.locator("#clip-video").evaluate("v => { v.muted = true; return v.play(); }")
            page.wait_for_function("() => document.querySelector('#clip-video').currentTime > 0.2", timeout=10000)
            self.check("the real clip decodes and plays", duration > 5.5, f"duration={duration}")
        except Exception as exc:
            self.check("the real clip decodes and plays", False, str(exc)[:300])
        context.close()
        browser.close()

    def create_flow(self, page, server) -> None:
        self.current = "create"
        page.goto(f"{server.base}/app#/create", wait_until="networkidle")
        page.locator("button[data-source='link']").click()
        page.locator("#generate").click()
        page.wait_for_selector(".toast", timeout=4000)
        self.check("empty link is rejected", "Paste a full video link" in page.locator(".toast").last.inner_text())

        captured: dict = {}
        fake = {"id": "fakejob", "title": "Fixture Episode", "status": "queued", "progress": 0.32,
                "stage": "Transcribing the episode", "clips": [], "created": time.time(),
                "source": {"name": "episode.webm"}, "duration": 60}

        def post_job(route):
            if route.request.method != "POST":
                return route.fallback()
            captured.update(json.loads(route.request.post_data or "{}"))
            route.fulfill(status=200, content_type="application/json", body=json.dumps(fake))

        def fake_job(route):
            if route.request.method == "DELETE":
                route.fulfill(status=200, content_type="application/json", body='{"ok":true}')
            else:
                route.fulfill(status=200, content_type="application/json", body=json.dumps(fake))

        page.route(re.compile(r"/api/jobs$"), post_job)
        page.route(re.compile(r"/api/jobs/fakejob$"), fake_job)
        page.locator("#url").fill("https://www.youtube.com/watch?v=fixture")
        page.locator("[data-count='custom']").click()
        page.locator("[name='max_clips']").fill("3")
        page.locator("[data-duration='range']").click()
        page.locator("[name='min_len']").fill("20")
        page.locator("[name='max_len']").fill("40")
        page.locator("[name='direction']").select_option("statement")
        page.locator("details.setup-group summary").click()
        page.locator("#style").select_option("minimal")
        page.locator(".toggle", has_text="Captions").click()
        page.locator("#generate").click()
        page.wait_for_url(re.compile(r"#/processing/fakejob"), timeout=10000)
        page.wait_for_function("() => document.body.innerText.includes('Transcription')", timeout=10000)
        options = captured.get("options") or {}
        self.check("project request carries the URL", captured.get("url", "").endswith("v=fixture"), str(captured))
        self.check("clip count is sent", options.get("max_clips") == 3, str(options))
        self.check("custom duration range is sent", options.get("min_len") == 20 and options.get("max_len") == 40, str(options))
        self.check("creative direction is sent", options.get("direction") == "statement", str(options))
        self.check("advanced settings are sent", options.get("style") == "minimal" and options.get("captions") is False, str(options))
        self.check("podcast mode is explicit", options.get("mode") == "podcast", str(options))
        self.check("brand is attached", bool(options.get("brand_id")), str(options))
        self.check("real processing stage is shown", "Transcribing the episode" in page.locator("#proc").inner_text())

        page.locator("[data-stop]").click()
        page.wait_for_selector("[data-yes]", timeout=4000)
        page.locator("[data-yes]").click()
        page.wait_for_url(re.compile(r"#/projects"), timeout=10000)
        self.check("project cancellation returns to Projects", page.url.endswith("#/projects"))

    def library_and_editor(self, page, server) -> None:
        self.current = "library"
        page.goto(f"{server.base}/app#/library", wait_until="networkidle")
        page.wait_for_selector(".clip-card", timeout=15000)
        self.check("finished clip appears in Library", page.locator(".clip-card").count() == 1)
        cover = page.locator(".clip-card img").first
        self.check("cover image has pixels", cover.evaluate("img => img.complete && img.naturalWidth > 0"))
        page.locator("#lib-search").fill("nothing matches this")
        page.wait_for_function("() => document.querySelector('#lib-grid').innerText.includes('Nothing matches')")
        self.check("library search filters", "Nothing matches" in page.locator("#lib-grid").inner_text())
        page.locator("#lib-search").fill("")
        page.locator("#lib-approval").select_option("recommended")
        self.check("library approval filter keeps the clip", page.locator(".clip-card").count() == 1)

        page.goto(f"{server.base}/app#/library/{JID}/{CID}", wait_until="networkidle")
        page.wait_for_selector("#clip-video", timeout=15000)
        self.check("clip player points at the clean cut for caption editing",
                   page.locator("#clip-video").get_attribute("src").endswith(f"/clips/{CID}/preview"))
        page.locator("[data-tab='captions']").click()
        page.wait_for_selector("[data-word]", timeout=8000)
        word_count = page.locator("[data-word]").count()
        self.check("caption words are editable", word_count >= 10, str(word_count))
        self.check("Caption Studio shows a real typographic preview for every style",
                   page.locator("[data-cap-style]").count() == 14, str(page.locator("[data-cap-style]").count()))
        page.locator("[data-cap-style='classic']").click()
        self.check("choosing a style updates the video overlay",
                   page.locator("[data-cap-style='classic']").get_attribute("aria-pressed") == "true"
                   and page.locator("#cap-overlay .cap-word").count() > 0)
        overlay_font = page.locator("#cap-overlay .cap-word").first.evaluate("el => getComputedStyle(el).fontFamily")
        self.check("overlay uses the same bundled face as the export", "Archivo Black" in overlay_font, overlay_font)
        page.locator("#cap-size").fill("130")
        self.check("type size changes the live preview", page.locator("#cap-size-out").inner_text() == "130")
        page.locator("[data-tab='edit']").click()
        page.locator("#e-title").fill("A thought that lands")
        page.locator("#save-meta").click()
        meta_ok = self.toast_contains(page, "Text saved", 6000)
        self.check("metadata save reports success", meta_ok, str(page.locator(".toast").all_inner_texts()))
        page.reload(wait_until="networkidle")
        page.wait_for_selector("#e-title", timeout=10000)
        self.check("metadata survives a refresh", page.locator("#e-title").input_value() == "A thought that lands")

        page.locator("#approve").click()
        page.wait_for_function("() => document.querySelector('#approve').innerText.includes('Approved')", timeout=8000)
        self.check("clip approval updates in the UI", "Approved" in page.locator("#approve").inner_text())

        brand = page.request.post(f"{server.base}/api/brands", data={"name": "Browser Brand",
                                                                    "tokens": {"name": "Browser Brand", "accent": "#336699"}}).json()["brand"]
        page.reload(wait_until="networkidle")
        page.wait_for_selector("#e-brand", timeout=10000)
        page.locator("#e-brand").select_option(brand["id"])
        page.wait_for_function("() => document.querySelector('#e-brand-hint').innerText.includes('Browser Brand')")
        self.check("brand selection updates the editor", "Browser Brand" in page.locator("#e-brand-hint").inner_text())
        render_status = []
        finish_payload: dict = {}

        def intercept_render(route):
            finish_payload.update(json.loads(route.request.post_data or "{}"))
            route.fulfill(status=200, content_type="application/json", body='{"ok":true}')

        page.route(re.compile(r"/clips/c1/render$"), intercept_render)
        page.locator("#save-finish").click()
        page.wait_for_selector(".toast", timeout=6000)
        self.check("finish request carries the selected brand", finish_payload.get("brand_id") == brand["id"],
                   str(finish_payload))
        self.check("finish request carries the sonic switch", finish_payload.get("sonic") is True, str(finish_payload))
        self.check("finish saves every finish toggle",
                   all(k in finish_payload for k in ("captions", "intro_cover", "outro", "watermark")),
                   str(finish_payload))
        page.locator("[data-tab='captions']").click()
        page.locator("[data-cap-style='classic']").click()
        page.locator("#cap-size").fill("132")
        page.locator("#save-cap").click()
        page.wait_for_timeout(500)
        cfg = finish_payload.get("caption_cfg") or {}
        self.check("caption save carries the full typography spec",
                   finish_payload.get("style") == "classic" and cfg.get("size") == 132
                   and cfg.get("font") == "archivo" and "letter_spacing" in cfg, str(finish_payload)[:400])
        self.check("manual emphasis is saved with captions", "highlight_words" in finish_payload, str(finish_payload)[:400])

    def brand_kit(self, page, server) -> None:
        self.current = "brands"
        page.goto(f"{server.base}/app#/brands", wait_until="networkidle")
        page.wait_for_selector("#new-brand", timeout=10000)
        page.locator("#new-brand").click()
        page.wait_for_selector("#m-name", timeout=4000)
        page.locator("#m-name").fill("Northwind")
        page.locator("[data-yes]").click()
        page.wait_for_url(re.compile(r"#/brands/br_"), timeout=10000)
        page.wait_for_selector("#brand-form", timeout=10000)
        self.check("new brand opens its editor", page.locator("#b-name").input_value() == "Northwind")
        page.locator("#b-accent").fill("#336699")
        page.locator("#b-ig").fill("northwind")
        page.locator("#b-tagline").fill("Conversations worth keeping")
        page.locator("#brand-form button[type='submit']").click()
        save_ok = self.toast_contains(page, "Brand saved", 8000)
        self.check("brand saves", save_ok, str(page.locator(".toast").all_inner_texts()))
        page.reload(wait_until="networkidle")
        page.wait_for_selector("#b-ig", timeout=10000)
        self.check("brand identity survives a refresh",
                   page.locator("#b-name").input_value() == "Northwind" and page.locator("#b-accent").input_value() == "#336699")

        from PIL import Image
        import io
        buf = io.BytesIO()
        Image.new("RGBA", (96, 96), (51, 102, 153, 255)).save(buf, "PNG")
        page.locator("#b-logo-input").set_input_files({"name": "logo.png", "mimeType": "image/png", "buffer": buf.getvalue()})
        logo_ok = self.toast_contains(page, "Brand logo saved", 12000)
        self.check("brand logo uploads", logo_ok, str(page.locator(".toast").all_inner_texts()))
        page.wait_for_load_state("networkidle")
        page.reload(wait_until="networkidle")
        page.wait_for_selector("#brand-form", timeout=10000)
        page.wait_for_selector("img[src*='/assets/logo']", timeout=8000)
        self.check("brand logo renders in the preview", page.locator("img[src*='/assets/logo']").first.is_visible())

        sound = Path(ARTIFACTS / "signature.wav")
        sound.parent.mkdir(parents=True, exist_ok=True)
        make_wav(sound)
        page.locator("#b-sonic-input").set_input_files(
            {"name": "signature.wav", "mimeType": "audio/wav", "buffer": sound.read_bytes()})
        has_handler = page.evaluate("() => !!document.querySelector('#b-sonic-input')?.onchange")
        self.check("signature input has an upload handler", has_handler)
        files = page.evaluate("() => { const i = document.querySelector('#b-sonic-input'); return i ? [i.files.length, i.files[0]?.name, i.accept] : null; }")
        self.check("signature file is selected", files is not None and files[0] == 1, str(files))
        page.locator("#b-sonic-input").evaluate("el => el.dispatchEvent(new Event('change', {bubbles: true}))")
        sonic_ok = self.check("signature sound uploads", self.toast_contains(page, "Signature sound saved", 12000),
                              str(page.locator(".toast").all_inner_texts()))
        if sonic_ok:
            page.wait_for_selector("audio[src*='/assets/sonic']", timeout=8000)
        self.check("signature sound has a preview", page.locator("audio[src*='/assets/sonic']").first.is_visible())
        bid = page.url.rsplit("/", 1)[-1]
        assets = page.request.get(f"{server.base}/api/brands/{bid}/assets/sonic")
        self.check("signature sound is served to its owner", assets.status == 200 and len(assets.body()) > 1000)

    def publishing(self, page, server) -> None:
        self.current = "publishing"
        page.goto(f"{server.base}/app#/publishing/{JID}/{CID}", wait_until="networkidle")
        page.wait_for_selector("#pub-clip", timeout=12000)
        self.check("publishing picks the finished clip", page.locator("#pub-clip").input_value().endswith(CID))
        page.locator("button[role='tab'][data-platform='instagram']").click()
        page.wait_for_function("() => document.body.innerText.includes('Instagram package')")
        self.check("platform tabs switch packages", "Instagram package" in page.locator("#package-panel").inner_text())
        page.locator("#p-caption").fill("A caption saved by the browser journey.")
        page.locator("#save-pkg").click()
        self.check("Instagram package saves", self.toast_contains(page, "Instagram package saved", 12000),
                   str(page.locator(".toast").all_inner_texts()))
        page.reload(wait_until="networkidle")
        page.wait_for_selector("#save-pkg", timeout=10000)
        page.locator("button[role='tab'][data-platform='instagram']").click()
        self.check("Instagram package survives a refresh",
                   "browser journey" in page.locator("#p-caption").input_value())
        page.locator("button[role='tab'][data-platform='youtube']").click()
        page.wait_for_function("() => document.body.innerText.includes('YouTube package')")
        readiness = page.locator(".checklist").inner_text()
        self.check("readiness names the missing account", "No platform account connected" in readiness, readiness)
        self.check("no publish action is offered without an account", page.locator("button", has_text=re.compile("Publish now", re.I)).count() == 0)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--update-baselines", action="store_true")
    parser.add_argument("--headed", action="store_true")
    parser.add_argument("--only", default=None)
    args = parser.parse_args()
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    suite = Suite(args.update_baselines, args.headed, args.only)
    print("Starting isolated Clipsora server…")
    server = StudioServer()
    try:
        server.start()
        print(f"Server: {server.base}")
        code = suite.run(server)
    finally:
        server.stop()
    (ARTIFACTS / "axe.json").write_text(json.dumps(suite.axe_findings, indent=1), encoding="utf-8")
    print(f"\n{suite.checks} checks, {len(suite.failures)} failed")
    for failure in suite.failures:
        print("  - " + failure)
    print(f"Axe violations recorded: {len(suite.axe_findings)} (see tests/browser/artifacts/axe.json)")
    print("\nAll browser tests passed!" if code == 0 else "\nBrowser tests failed.")
    return code


if __name__ == "__main__":
    sys.exit(main())
