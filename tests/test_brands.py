"""Brand Kit: several brands, one voice each, and the decisions a render reads from them."""
import json
import os
import sys
import tempfile
import wave
from pathlib import Path

os.environ["CLIPSORA_DATA"] = tempfile.mkdtemp()
os.environ["DATABASE_URL"] = ""
sys.path.insert(0, ".")

from studio import brands, db  # noqa: E402

fails = []


def check(name, ok, extra=""):
    print(("PASS " if ok else "FAIL ") + name + (f"   {extra}" if extra and not ok else ""))
    ok or fails.append(name)


def _raises(fn):
    try:
        fn()
        return False
    except brands.BrandError:
        return True


def _user(uid):
    with db.engine.begin() as conn:
        if not conn.execute(db.users.select().where(db.users.c.id == uid)).first():
            conn.execute(db.users.insert().values(id=uid, email=f"{uid}@example.com", created_at=1.0))


def main():
    db.init()
    user = "u_brand_test"
    _user(user)
    _user("u_other")

    # 1. Defaults and validation
    t = brands.normalize_tokens({"name": "  Northwind  ", "ig_handle": "@northwind",
                                 "accent": "#d99045", "sonic": {"gain_db": -900}})
    check("name is trimmed", t["name"] == "Northwind")
    check("handle loses its @", t["ig_handle"] == "northwind")
    check("accent is normalised", t["accent"] == "#D99045")
    check("gain is clamped to a sane range", -24.0 <= t["sonic"]["gain_db"] <= 6.0, str(t["sonic"]))
    try:
        brands.normalize_tokens({"name": "X", "accent": "purple"})
        bad = False
    except brands.BrandError:
        bad = True
    check("an invalid colour is rejected", bad)
    check("unknown keys do not survive", "drop_table" not in brands.normalize_tokens({"name": "X", "drop_table": 1}))

    # 2. One brand per account is created from the legacy settings, once.
    made = brands.ensure_default(user, {"brand_name": "Old Name", "brand_color": "#123456",
                                        "ig_handle": "oldhandle"})
    check("default brand is created from legacy settings", made["tokens"]["name"] == "Old Name", str(made))
    check("legacy accent is carried over", made["tokens"]["accent"] == "#123456")
    check("ensure_default is idempotent", brands.ensure_default(user)["id"] == made["id"])
    check("the default brand is flagged", brands.default(user)["id"] == made["id"])

    # 3. A second brand, and switching the default
    second = brands.create(user, "Second Show", {"accent": "#224466"}, is_default=True)
    check("second brand is created", second["tokens"]["name"] == "Second Show")
    check("only one brand is default", brands.default(user)["id"] == second["id"])
    check("list returns both", len(brands.list_brands(user)) == 2)
    with_default = brands.update(user, made["id"], {"is_default": True})
    check("default can move", brands.default(user)["id"] == made["id"] and with_default["name"] == "Old Name")

    # 4. Nested updates merge instead of wiping the rest
    updated = brands.update(user, second["id"], {"tokens": {"sonic": {"gain_db": -6}}})
    check("nested patch keeps other tokens", updated["tokens"]["name"] == "Second Show")
    check("nested patch changes the value", updated["tokens"]["sonic"]["gain_db"] == -6.0)
    check("unedited sonic fields survive", updated["tokens"]["sonic"]["target_lufs"] == -14.0)

    # 5. Isolation and deletion
    other = brands.create("u_other", "Someone Else")
    check("brands are per account", len(brands.list_brands(user)) == 2 and len(brands.list_brands("u_other")) == 1)
    check("a brand from another account is invisible", brands.get(user, other["id"]) is None)
    brands.delete(user, second["id"])
    check("deleting a brand removes it", len(brands.list_brands(user)) == 1)
    check("a remaining brand becomes default", brands.default(user) is not None)

    # 6. Outro adapts to the story and never covers the last words
    b = brands.get(user, made["id"])
    short = brands.outro_plan(b, "minimalist", 24.0, speech_end=23.0, clip_end=24.0)
    long = brands.outro_plan(b, "editorial", 120.0, speech_end=119.0, clip_end=120.0)
    check("short clip gets a brief outro", short["duration"] <= 1.2, str(short))
    check("long clip gets a more deliberate outro", long["duration"] > short["duration"], str(long))
    check("outro starts after the final words", long["start"] >= 119.25, str(long))
    cinematic = brands.outro_plan(b, "documentary", 30.0, speech_end=29.0, clip_end=30.0)
    check("cinematic falls back to a wordmark on a short clip", cinematic["style"] == "wordmark", str(cinematic))
    check("outro never claims to cover the final words", long["covers_final_words"] is False)

    # 7. CTA: one action, platform-specific, brand override wins
    yt = brands.cta_for(b, "youtube", "editorial")
    ig = brands.cta_for(b, "instagram", "editorial")
    check("YouTube and Instagram get different CTAs", yt != ig, f"{yt} / {ig}")
    check("YouTube asks for a subscription", "Subscribe" in yt or "subscribe" in yt, yt)
    custom = brands.update(user, b["id"], {"tokens": {"ctas": {"youtube": "Join the channel."}}})
    check("a custom CTA wins", brands.cta_for(custom, "youtube", "kinetic") == "Join the channel.")

    # 8. Sonic identity: quiet, bounded, and limited below full scale
    flt = brands.sonic_mix_filter(2.0, b["tokens"]["sonic"], voice_seconds=45)
    check("logo is delayed to its cue", "adelay=2000|2000" in flt, flt)
    check("logo gain is applied", "volume=-3.0dB" in flt, flt)
    check("fades are present", "afade=t=in" in flt and "afade=t=out" in flt, flt)
    check("speech is loudness-normalised", "loudnorm=I=-14.0" in flt, flt)
    check("output is hard-limited below full scale", "alimiter=limit=0.891" in flt, flt)
    check("logo is trimmed to the brand maximum", "atrim=0:4.000" in flt, flt)
    check("the mix ends with the video, not the logo", "duration=first" in flt, flt)

    # 9. A real WAV can be checked without ffmpeg: this is the file a signature sound would be.
    wav = Path(tempfile.mkdtemp()) / "logo.wav"
    with wave.open(str(wav), "w") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(48000)
        w.writeframes(b"\x00\x10" * 24000)          # 0.5 s, quiet
    with wave.open(str(wav)) as w:
        check("signature sound is a readable 48 kHz file", w.getframerate() == 48000 and w.getnframes() == 24000)

    # 10. Consistency validator
    perfect = {"brand_name": "Old Name", "brand_color": "#123456", "ig_handle": "oldhandle",
               "direction": "editorial", "outro_style": "auto", "platform": "youtube",
               "cta": brands.cta_for(b, "youtube", "editorial")}
    check("a consistent reel has no issues", brands.consistency_issues(perfect, b) == [])
    wrong = dict(perfect, brand_color="#FF0000", ig_handle="someoneelse")
    issues = brands.consistency_issues(wrong, b)
    check("a wrong accent is caught", any("colour" in i.lower() for i in issues), str(issues))
    check("a wrong handle is caught", any("handle" in i.lower() for i in issues), str(issues))

    # 11. Per-brand assets are stored for their owner, replace cleanly and delete safely.
    from PIL import Image
    import io
    buf = io.BytesIO()
    Image.new("RGBA", (80, 80), (51, 102, 153, 255)).save(buf, "PNG")
    with_assets = brands.save_asset(user, b["id"], "logo", buf.getvalue(), ".png", {"kind": "test"})
    logo_path = with_assets["tokens"]["logo"]
    check("brand logo is stored", bool(logo_path) and Path(logo_path).is_file(), logo_path)
    check("brand logo belongs to its brand", brands.asset_row(user, b["id"], "logo") is not None)
    check("another account cannot read the logo", brands.asset_row("u_other", b["id"], "logo") is None)
    check("a foreign brand cannot receive an asset",
          _raises(lambda: brands.save_asset("u_other", b["id"], "logo", b"x", ".png")))
    with_assets = brands.save_asset(user, b["id"], "sonic", wav.read_bytes(), ".wav", {"duration": 0.5})
    sonic_path = with_assets["tokens"]["sonic"]["asset"]
    check("signature sound is stored", bool(sonic_path) and Path(sonic_path).is_file(), sonic_path)
    check("signature sound resolves through the renderer helper", brands.asset_path(sonic_path) == sonic_path)
    replaced = brands.save_asset(user, b["id"], "logo", buf.getvalue(), ".png", {"kind": "replacement"})
    check("replacing a logo keeps one row", len([r for r in brands.list_brands(user) if r["id"] == b["id"]]) == 1)
    check("replacement keeps the logo usable", Path(replaced["tokens"]["logo"]).is_file())
    brands.delete_asset(user, b["id"], "logo")
    check("removing a logo clears the token and file",
          not brands.get(user, b["id"])["tokens"]["logo"] and not Path(logo_path).exists())
    check("removing a logo leaves the sound alone",
          bool(brands.get(user, b["id"])["tokens"]["sonic"]["asset"]))

    # 12. A clip's brand and sonic override survive the re-render request and are written to job.json.
    from studio import jobs
    d = Path(tempfile.mkdtemp())
    jid = "j_brand_clip"
    job = {"id": jid, "dir": str(d), "user": user, "kind": "video", "title": "t", "created": 1.0,
           "options": {}, "clips": [{"id": "c1", "start": 0.0, "end": 6.0,
                                      "style": "bounce", "layout": "blur", "status": "done"}]}
    jobs._jobs[jid] = job
    old_put = jobs._q.put
    jobs._q.put = lambda *a, **k: None
    try:
        jobs.request_render(jid, "c1", {"brand_id": "br_owner", "sonic": False, "sonic_gain_db": -8})
        saved = json.loads((d / "job.json").read_text(encoding="utf-8"))["clips"][0]
        check("clip brand id is persisted", saved.get("brand_id") == "br_owner", str(saved.get("brand_id")))
        check("clip sonic switch is persisted", saved.get("sonic") is False, str(saved.get("sonic")))
        check("clip sonic gain is persisted and bounded", saved.get("sonic_gain_db") == -8.0, str(saved.get("sonic_gain_db")))
        jobs.request_render(jid, "c1", {"style": "classic", "caption_cfg": {"preset": "classic", "size": 120,
                                         "letter_spacing": 4, "max_words": 2}, "highlight_words": ["BUILD", "money"]})
        saved = json.loads((d / "job.json").read_text(encoding="utf-8"))["clips"][0]
        check("caption typography is persisted with the clip",
              saved["caption_cfg"]["size"] == 120 and saved["caption_cfg"]["letter_spacing"] == 4
              and saved["caption_cfg"]["max_words"] == 2, str(saved.get("caption_cfg")))
        check("manual emphasis is cleaned and persisted", saved.get("highlight_words") == ["BUILD", "money"],
              str(saved.get("highlight_words")))
    finally:
        jobs._q.put = old_put
        jobs._jobs.pop(jid, None)

    if fails:
        print(f"\n{len(fails)} failed: " + ", ".join(fails))
        sys.exit(1)
    print("\nAll brand tests passed!")


if __name__ == "__main__":
    main()
