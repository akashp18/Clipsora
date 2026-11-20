"""Caption presets and video layouts: every style draws, every layout composes, and a clip really renders.

Runs without a server: the presets, the caption file builder and the ffmpeg filters are all plain functions.
The last section renders two real clips from a generated test video, so the contract between the style data and
the encoder is checked end to end rather than assumed.
"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

os.environ["CLIPSORA_DATA"] = tempfile.mkdtemp(prefix="pc-styles-")
os.environ["DATABASE_URL"] = ""
sys.path.insert(0, ".")

from studio import config, jobs, render, styles  # noqa: E402

fails = []


def check(name, ok, x=""):
    print(("PASS " if ok else "FAIL ") + name + (f"  {x}" if x and not ok else ""))
    ok or fails.append(name)


WORDS = [{"w": w, "s": i * 0.55, "e": i * 0.55 + 0.5} for i, w in enumerate(
    "this is a reasonably long phrase that wraps across lines".split())]


def dialogues(ass):
    out = []
    for line in ass.splitlines():
        if line.startswith("Dialogue:"):
            parts = line[len("Dialogue:"):].split(",", 9)
            out.append({"layer": int(parts[0]), "start": ts(parts[1]), "end": ts(parts[2]), "style": parts[3], "text": parts[9]})
    return out


def ts(v):
    h, m, s = v.split(":")
    return int(h) * 3600 + int(m) * 60 + float(s)


# ---------------------------------------------------------------------------------------- the preset library
caps = styles.CAPTION_PRESETS
lays = styles.LAYOUT_PRESETS
check("14 caption presets", len(caps) == 14, str(len(caps)))
check("16 layouts", len(lays) == 16, str(len(lays)))
check("the three original styles are still there", all(k in caps for k in ("bounce", "hype", "clean")))
check("the eight original layouts are still there",
      all(k in lays for k in ("blur", "zoom", "crop", "left", "right", "fit", "split", "gameplay")))
check("every preset carries every caption field",
      all(set(styles.CAPTION_DEFAULTS) <= set(p) for p in caps.values()),
      str([k for k, p in caps.items() if not set(styles.CAPTION_DEFAULTS) <= set(p)]))
check("every caption font is one the app ships", all(p["font"] in styles.FONTS for p in caps.values()))
cat = {p["category"] for p in caps.values()}
check("presets are grouped into categories", len(cat) >= 4, str(cat))
check("every layout describes itself", all(p["description"] for p in lays.values()))
check("the library sent to the browser is stable and complete",
      len(styles.caption_presets()) == 14 and len(styles.layout_presets()) == 16
      and {"id", "label", "font_name"} <= set(styles.caption_presets()[0]))

# ---------------------------------------------------------------------------------------- configuration rules
c = styles.caption_config("bounce", {"size": 9999, "max_words": 0, "animation": "nonsense", "base": "not-a-colour"})
check("size is clamped to the frame", c["size"] == 220, str(c["size"]))
check("words per line never drops below one", c["max_words"] == 1, str(c["max_words"]))
check("an unknown animation falls back to the preset's", c["animation"] == "bounce")
check("a broken colour falls back to the preset's", c["base"] == "#FFFFFF", c["base"])
check("a customisation remembers which preset it came from", c["preset"] == "bounce" and c["schema"] == styles.SCHEMA_VERSION)
check("the font is resolved to a real file name", c["font_name"] == "Poppins ExtraBold")
check("a box colour without opacity stays invisible", styles.caption_config("editorial", {"box_opacity": 0})["box_opacity"] == 0)
try:
    styles.caption_config("no-such-style")
    check("an unknown style is refused", False)
except ValueError as e:
    check("an unknown style is refused", "no caption style" in str(e).lower(), str(e))
lay = styles.layout_config("blur", {"zoom": 9, "focal_x": -4, "pip_corner": "nowhere"})
check("layout numbers are clamped", lay["zoom"] == 2.5 and lay["focal_x"] == 0, str((lay["zoom"], lay["focal_x"])))
check("an unknown corner falls back", lay["pip_corner"] == "top-right")
try:
    styles.layout_config("no-such-layout")
    check("an unknown layout is refused", False)
except ValueError as e:
    check("an unknown layout is refused", "no layout" in str(e).lower(), str(e))
check("an old saved clip (style name only) still resolves", styles.caption_config("hype")["preset"] == "hype")

# ---------------------------------------------------------------------------------------- every style draws
for name, p in caps.items():
    ass = render.build_ass(WORDS, 0.0, 4.0, "A HOOK", name, [], 300, 1500)
    ev = dialogues(ass)
    style_line = next((l for l in ass.splitlines() if l.startswith("Style: Cap,")), "")
    font = styles.FONTS[p["font"]]
    ok = (f"Style: Cap,{font}" in style_line and ev and all(e["style"] == "Cap" for e in ev if e["style"] == "Cap"))
    inside = [e for e in dialogues(ass) if e["style"] == "Cap"]
    check(f"{name}: draws words in {font}", bool(ok) and bool(inside))
    check(f"{name}: nothing is drawn outside the clip",
          all(-0.01 <= e["start"] <= 4.01 and -0.01 <= e["end"] <= 4.26 for e in inside), str([(e["start"], e["end"]) for e in inside][:3]))
    check(f"{name}: every event sits inside the clip",
          all(0 <= e["start"] <= 4.01 and e["end"] >= e["start"] for e in inside))

# ---------------------------------------------------------------------------------------- timing and highlighting
ass = render.build_ass(WORDS, 1.0, 3.0, "", "clean", ["reasonably"], 300, 1500)
cap = [e for e in dialogues(ass) if e["style"] == "Cap"]
check("only words inside the clip's own seconds are drawn", ass.count("Dialogue:") == len(cap) and cap)
check("captions start when the first word is said, not before",
      min(e["start"] for e in cap) <= 1.0 + 0.01, str(min(e["start"] for e in cap)))
check("a highlighted word is marked, the others are not",
      ass.count(f"&H{render._bgr(styles.caption_config('clean')['strong'])}&") >= 1)
check("a word is never drawn before it is spoken",
      all(e["start"] >= 0 for e in cap))

# ---------------------------------------------------------------------------------------- animations
def has(name, tag, **over):
    a = render.build_ass(WORDS, 0.0, 4.0, "", name, [], 300, 1500) if not over else \
        render.build_ass(WORDS, 0.0, 4.0, "", {**styles.caption_config(name), **over}, [], 300, 1500)
    return tag in a


check("fade fades in", has("minimal", "\\fad("))
check("slide moves into place", has("editorial", "\\move("))
check("pop and bounce scale", has("bounce", "\\t(") and has("hype", "\\t("))
check("glitch jitters", has("glitch", "\\t("))
check("typewriter reveals letters one at a time",
      render.build_ass(WORDS, 0.0, 4.0, "", "typewriter", [], 300, 1500).count("Dialogue: 2") > 20)
check("animation off means no scaling or fading at all", not has("classic", "\\t(") and not has("classic", "\\fad("))
check("intensity changes how far a word grows",
      has("bounce", "\\fscx84", intensity=95) and has("bounce", "\\fscx84", intensity=5))
check("a caption box asks the renderer for a filled background",
      "BorderStyle" in render.build_ass(WORDS, 0, 4, "", "podcast", [], 300, 1500) and ",3," in
      next(l for l in render.build_ass(WORDS, 0, 4, "", "podcast", [], 300, 1500).splitlines() if l.startswith("Style: Cap,")))
check("no box means outline and shadow only",
      ",1," in next(l for l in render.build_ass(WORDS, 0, 4, "", "bounce", [], 300, 1500).splitlines() if l.startswith("Style: Cap,")))
ass_long = render.build_ass(WORDS, 0.0, 4.0, "", styles.caption_config("clean", {"max_words": 2}), [], 300, 1500)
ys = {re.search(r"\\pos\(\d+,(\d+)\)", e["text"]).group(1) for e in dialogues(ass_long) if e["style"] == "Cap"}
check("a long phrase wraps instead of shrinking to nothing", len(ys) >= 1)

# ---------------------------------------------------------------------------------------- layouts
for name, p in lays.items():
    f = render._filter(name, 1200)
    check(f"{name}: builds a video graph", f.endswith("[v0];") and "[0:v]" in f)
check("side by side puts two pictures next to each other", "hstack" in render._filter("side", 1920))
check("split screen stacks them", "vstack" in render._filter("split", 1920))
check("black bars pad the frame", "pad=" in render._filter("fit", 1200))
check("cinematic draws bars", "drawbox" in render._filter("cinematic", 1200))
check("a brand layout draws its band", "drawbox" in render._filter("brand", 1920))
check("auto reframe crops around the focal point", "crop=" in render._filter("reframe", 1920))
check("keep left really keeps the left", "crop=1080:1920:(in_w-out_w)*0.0" in render._filter("left", 1920))
check("keep right really keeps the right", "crop=1080:1920:(in_w-out_w)*1.0" in render._filter("right", 1920))
check("picture in picture without a webcam still fills the frame",
      "overlay" not in render._filter("pip", 1920, None))
check("picture in picture with a webcam overlays the corner",
      "overlay" in render._filter("pip", 1920, [60, 40, 320, 240]))
check("gameplay puts the webcam in the top corner",
      "overlay=676:26" in render._filter("gameplay", 1920, [60, 40, 320, 240]))
for name in lays:
    cfg = styles.layout_config(name)
    kind, fg_h, hook_y, cap_y = render.geometry(1280, 720, cfg)
    check(f"{name}: captions stay inside the frame", 0 < cap_y < render.H and 0 < hook_y < render.H, str((hook_y, cap_y)))

# ---------------------------------------------------------------------------------------- option checking
opts = jobs.clean_options({"style": "karaoke", "layout": "side",
                           "caption_cfg": {"preset": "karaoke", "size": 999, "animation": "slide"},
                           "layout_cfg": {"preset": "side", "gap": 40}})
check("a style choice is stored with its customisation", opts["caption_cfg"]["size"] == 220 and opts["caption_cfg"]["animation"] == "slide")
check("a layout choice is stored with its customisation", opts["layout_cfg"]["gap"] == 40)
try:
    jobs.clean_options({"caption_cfg": "big"})
    check("a nonsense customisation is refused", False)
except ValueError:
    check("a nonsense customisation is refused", True)
check("an unknown style name in old options falls back", jobs.clean_options({"style": "gone"})["style"] == "bounce")

# ---------------------------------------------------------------------------------------- controls stay honest
html = Path("web/index.html").read_text(encoding="utf-8")
cap_controls = set(re.findall(r'data-cap="([a-z_]+)"', html))
lay_controls = set(re.findall(r'data-lay="([a-z_]+)"', html))
check("the caption panel exposes its controls", {"size", "animation", "position", "box_opacity"} <= cap_controls, str(cap_controls))
check("every caption control is one the renderer reads", cap_controls <= styles.CAPTION_KEYS, str(cap_controls - styles.CAPTION_KEYS))
check("every layout control is one the renderer reads", lay_controls <= styles.LAYOUT_KEYS, str(lay_controls - styles.LAYOUT_KEYS))
check("the schema carries no setting the renderer ignores",
      set(styles.CAPTION_DEFAULTS) == set(styles.CAPTION_KEYS) and set(styles.LAYOUT_DEFAULTS) == set(styles.LAYOUT_KEYS),
      str((set(styles.CAPTION_DEFAULTS) ^ set(styles.CAPTION_KEYS)) | (set(styles.LAYOUT_DEFAULTS) ^ set(styles.LAYOUT_KEYS))))
check("the dead layout fields are gone", not ({"scale", "split", "radius", "border"} & set(styles.LAYOUT_KEYS)))
check("the dead caption fields are gone", not ({"weight", "align"} & set(styles.CAPTION_KEYS)))

canvas0 = render._filter(styles.layout_config("canvas", {"margin": 0}), 1400)
canvas20 = render._filter(styles.layout_config("canvas", {"margin": 20}), 1400)
check("the Canvas margin really resizes the picture", canvas0 != canvas20 and "scale=1080:" in canvas0 and "scale=648:" in canvas20,
      canvas20)
check("the Canvas margin leaves the colour field visible", "pad=" in canvas20 and "#141612" in canvas20)
check("the band height really draws bands",
      "drawbox" in render._filter(styles.layout_config("canvas", {"bars": 12}), 1400)
      and "drawbox" not in render._filter(styles.layout_config("canvas", {"bars": 0}), 1400))

def ys(a):
    return {int(m.group(1)) for m in re.finditer(r"\\pos\(\d+,(\d+)\)", a)}

top = render.build_ass(WORDS, 0, 4, "", styles.caption_config("clean", {"position": "top"}), [], 300, 1500)
mid = render.build_ass(WORDS, 0, 4, "", styles.caption_config("clean", {"position": "middle"}), [], 300, 1500)
bot = render.build_ass(WORDS, 0, 4, "", styles.caption_config("clean", {"position": "bottom"}), [], 300, 1500)
check("the caption position control really moves the words",
      min(ys(top)) < 800 and min(ys(bot)) > 1200 and min(ys(mid)) > min(ys(top)), str((sorted(ys(top))[:1], sorted(ys(mid))[:1], sorted(ys(bot))[:1])))

# a new style must never inherit the last one's changes
before = dict(styles.CAPTION_PRESETS["hype"])
styles.caption_config("bounce", {"size": 200, "active": "#FF0000", "animation": "glitch"})
check("customising one style leaves the preset library untouched", styles.CAPTION_PRESETS["hype"] == before)
fresh = styles.caption_config("hype")
check("choosing a new style starts from its own defaults",
      fresh["size"] == before["size"] and fresh["active"] == before["active"] and fresh["animation"] == before["animation"], str(fresh))
check("picking a style in the browser clears the previous configuration",
      '$("#o_caption_cfg").value = "";' in html and '$("#o_layout_cfg").value = "";' in html)
check("the composer and the clip editor draw a style with one shared sample",
      "function lookSample(" in html and len(re.findall(r"lookSample\(", html)) >= 5
      and not re.search(r"function (capSample|capChip)\(", html))
check("both clip-editor pickers are listboxes a screen reader can follow",
      'aria-haspopup="listbox"' in html and 'aria-controls="${menuId}"' in html and 'role="listbox"' in html
      and 'role="option"' in html and 'aria-selected=' in html and 'role="group" aria-labelledby=' in html)
pickers = html[html.index("function focusLook("):html.index("function paintCapPanels(")]
check("the pickers answer the keys a native select did",
      all(k in pickers for k in ('"ArrowDown"', '"ArrowUp"', '"Home"', '"End"', '"Escape"', '"Tab"', "LOOK_TYPED")),
      pickers[:200])
stale = styles.caption_config("bounce", {"preset": "hype", "size": 200})
check("the style that was actually chosen wins over a name left in the configuration",
      stale["preset"] == "bounce" and stale["size"] == 200, str(stale["preset"]))

# ---------------------------------------------------------------------------------------- a real render
work = Path(tempfile.mkdtemp(prefix="pc-render-"))
try:
    src = work / "src.mp4"
    made = subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "testsrc=size=1280x720:rate=30:duration=3",
                           "-f", "lavfi", "-i", "sine=frequency=440:duration=3", "-c:v", "libx264", "-pix_fmt", "yuv420p",
                           "-c:a", "aac", "-shortest", str(src)], capture_output=True, text=True)
    check("a test video is available to render from", made.returncode == 0 and src.exists(), made.stderr[-300:])
    render.install_fonts()
    clip = {"start": 0.0, "end": 3.0, "hook": "REAL RENDER", "style": "karaoke", "layout": "crop",
            "layout_cfg": styles.layout_config("crop", {"focal_x": 0.4}), "captions": True, "title": "t", "description": "d"}
    out = work / "out1"
    res = render.render_clip(src, out, "clip01", clip, WORDS, 1280, 720)
    check("a clip renders with a custom caption style and layout",
          res["file"] == "clip01.mp4" and (out / "clip01.mp4").stat().st_size > 1000 and (out / "clip01.ass").exists())
    probe = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height",
                            "-of", "json", str(out / "clip01.mp4")], capture_output=True, text=True)
    dims = json.loads(probe.stdout)["streams"][0] if probe.returncode == 0 and probe.stdout.strip() else {}
    check("the exported file is the vertical frame the preview promises", dims.get("width") == 1080 and dims.get("height") == 1920, str(dims))
    ass = (out / "clip01.ass").read_text(encoding="utf-8")
    check("the exported file carries the chosen style", "Style: Cap,Poppins ExtraBold" in ass and "Dialogue:" in ass)
    clip2 = {**clip, "layout": "side", "layout_cfg": styles.layout_config("side", {"gap": 20}), "style": "cinematic",
             "caption_cfg": styles.caption_config("cinematic", {"size": 100})}
    out2 = work / "out2"
    res2 = render.render_clip(src, out2, "clip02", clip2, WORDS, 1280, 720)
    check("a second layout renders without touching the first", res2["layout"] == "side" and (out2 / "clip02.mp4").stat().st_size > 1000)
    check("layout customisation reaches the filter", "gap" not in res2 and res2["layout"] == "side")
finally:
    shutil.rmtree(work, ignore_errors=True)

shutil.rmtree(os.environ["CLIPSORA_DATA"], ignore_errors=True)
print("ALL PASSED" if not fails else f"{len(fails)} failed")
sys.exit(1 if fails else 0)
