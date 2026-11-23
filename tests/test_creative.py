"""Creative directions: selection, tokens and render parity.

No server and no ffmpeg: the point is that the direction a clip is given resolves into settings the existing
renderer already understands, and that the same content always chooses the same direction.
"""
import os
import sys
import tempfile

from fastapi.testclient import TestClient

sys.path.insert(0, ".")

fails = []


def check(name, ok, extra=""):
    print(("PASS " if ok else "FAIL ") + name + (f"   {extra}" if extra and not ok else ""))
    ok or fails.append(name)


def main(data):
    os.environ.update(CLIPSORA_DATA=data, DATABASE_URL="", CLIPSORA_ACCOUNTS="0")
    from studio import creative, db, server, styles

    db.init()

    # 1. Five systems, stable ids
    check("five creative directions exist", len(creative.names()) == 5, str(creative.names()))
    check("editorial is present", creative.is_direction("editorial"))
    check("an unknown name is not a direction", not creative.is_direction("neon-purple"))

    # 2. Content-aware, deterministic selection
    editorial = creative.choose(["Business"], {"hook_strength": 18, "emotional_impact": 10, "value": 13}, 70,
                                "the company grew because of how it priced the product")
    check("a business explanation chooses The Editorial", editorial == "editorial", editorial)
    kinetic = creative.choose(["Humour"], {"hook_strength": 20, "emotional_impact": 16, "value": 8}, 25,
                              "and then he just kept going and going and nobody could stop laughing")
    check("a fast funny exchange chooses The Kinetic", kinetic == "kinetic", kinetic)
    minimalist = creative.choose(["Life lessons"], {"hook_strength": 12, "emotional_impact": 19, "value": 10}, 60,
                                 "it took me years to understand what my father meant that day")
    check("an emotional reflection chooses The Minimalist", minimalist == "minimalist", minimalist)
    statement = creative.choose(["Motivation"], {"hook_strength": 24, "emotional_impact": 12, "value": 9}, 22,
                                "stop waiting for permission")
    check("a short declaration chooses The Statement", statement == "statement", statement)
    again = creative.choose(["Business"], {"hook_strength": 18, "emotional_impact": 10, "value": 13}, 70,
                            "the company grew because of how it priced the product")
    check("the same clip always gets the same direction", editorial == again)

    # 3. A brand preference wins, a broken one does not break the clip
    check("a chosen direction is respected", creative.choose(["Business"], {}, 20, "", preferred="documentary") == "documentary")
    check("an invalid preference falls back to the best fit",
          creative.is_direction(creative.choose(["Business"], {}, 20, "", preferred="vaporwave")))

    # 4. Every direction resolves to settings the renderer already accepts
    for name in creative.names():
        cfg = creative.render_settings(name)
        check(f"{name}: style is a real caption preset", cfg["style"] in styles.CAPTION_PRESETS, cfg["style"])
        check(f"{name}: layout is real", cfg["layout"] in styles.LAYOUT_PRESETS or cfg["layout"] == "auto", cfg["layout"])
        # Colours are normalised to lower case when a saved config is read back, so compare them that way.
        norm = lambda d: {k: (v.lower() if isinstance(v, str) and v.startswith("#") else v)
                          for k, v in d.items()}
        rebuilt = styles.caption_config(cfg["caption_cfg"]["preset"], cfg["caption_cfg"])
        check(f"{name}: caption settings round-trip", norm(rebuilt) == norm(cfg["caption_cfg"]))
        check(f"{name}: captions stay short enough to read", int(cfg["caption_cfg"]["max_words"]) <= 5,
              str(cfg["caption_cfg"]["max_words"]))
        check(f"{name}: caption size stays on screen", 40 <= int(cfg["caption_cfg"]["size"]) <= 220)
        if cfg["layout_cfg"]:
            check(f"{name}: layout settings round-trip",
                  norm(styles.layout_config(cfg["layout_cfg"]["preset"], cfg["layout_cfg"])) == norm(cfg["layout_cfg"]))
        check(f"{name}: declares an accessible reduced-motion fallback",
              bool(creative.SYSTEMS[name]["accessibility"].get("reduced_motion")))

    # 5. Tokens the UI needs are present and versioned
    cat = creative.catalog()
    check("catalog has every direction", len(cat) == 5)
    first = cat[0]
    for key in ("id", "label", "purpose", "typography", "colour", "motion", "safe_area", "cover", "outro", "cta", "audio", "render"):
        check(f"catalog entry carries {key}", key in first)
    check("catalog is versioned", creative.SCHEMA_VERSION >= 1)
    check("each system names its YouTube CTA", bool(creative.cta_for("editorial", "youtube")))
    check("each system names its Instagram CTA", bool(creative.cta_for("editorial", "instagram")))

    # 6. Job options accept the new settings and reject nonsense
    from studio import jobs
    opts = jobs.clean_options({"direction": "kinetic", "duration_mode": "content"})
    check("a job can ask for a direction", opts["direction"] == "kinetic")
    bad = jobs.clean_options({"direction": "vaporwave", "duration_mode": "fixed"})
    check("an unknown direction falls back to auto", bad["direction"] == "auto")
    check("an unknown duration mode falls back to content", bad["duration_mode"] == "content")

    # 7. The API exposes the catalog
    client = TestClient(server.app, base_url="http://127.0.0.1:8765",
                        headers={"Host": "127.0.0.1:8765", "Origin": "http://127.0.0.1:8765",
                                 "Sec-Fetch-Site": "same-origin"})
    r = client.get("/api/creative/directions")
    check("GET /api/creative/directions returns 200", r.status_code == 200, str(r.status_code))
    check("the API returns five directions", len(r.json().get("directions", [])) == 5)
    r_one = client.get("/api/creative/directions/editorial")
    check("GET one direction returns 200", r_one.status_code == 200)
    check("an unknown direction is a 404", client.get("/api/creative/directions/nope").status_code == 404)


if __name__ == "__main__":
    temp_dir = tempfile.mkdtemp(prefix="clipsora-creative-test-")
    try:
        main(temp_dir)
    finally:
        import shutil
        shutil.rmtree(temp_dir, ignore_errors=True)
    if fails:
        print(f"\n{len(fails)} test(s) failed: {', '.join(fails)}")
        sys.exit(1)
    print("\nAll creative direction tests passed!")
