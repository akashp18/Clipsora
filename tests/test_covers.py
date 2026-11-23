"""Cover intelligence and composition: measured, deterministic, and free of ffmpeg.

Every case builds its own synthetic frame, so the expected ranking is obvious: a sharp frame must beat a
blurred one, a mid-exposed frame must beat a near-black one, and a quiet lower third must beat a busy one.
The composition checks re-measure the drawn lines against the promised text box, which is what "no overflow"
actually means.
"""
import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("CLIPSORA_DATA", tempfile.mkdtemp())
os.environ.setdefault("DATABASE_URL", "")
sys.path.insert(0, ".")

from PIL import Image, ImageDraw, ImageFilter  # noqa: E402

from studio import covers  # noqa: E402
from studio.brands import DEFAULT_TOKENS, normalize_tokens  # noqa: E402

fails = []


def check(name, ok, extra=""):
    print(("PASS " if ok else "FAIL ") + name + (f"   {extra}" if extra and not ok else ""))
    ok or fails.append(name)


def scene(busy_bottom=False, brightness=110):
    img = Image.new("RGB", (720, 1280), (brightness, brightness - 8, brightness - 14))
    d = ImageDraw.Draw(img)
    d.ellipse([210, 210, 510, 620], fill=(196, 152, 120))          # a "face" in the upper middle
    d.rectangle([250, 640, 470, 1000], fill=(52, 58, 66))
    for x in range(24, 210, 6):                                      # fine detail the blur can destroy
        d.line([(x, 120), (x, 440)], fill=(70, 76, 84), width=2)
    for x in range(520, 700, 6):
        d.line([(x, 120), (x, 440)], fill=(70, 76, 84), width=2)
    if busy_bottom:
        for y in range(760, 1260, 26):
            for x in range(20, 700, 40):
                d.line([(x, y), (x + 24, y + 14)], fill=(230, 230, 230), width=3)
    return img


def main():
    sharp = scene()
    blurred = sharp.filter(ImageFilter.GaussianBlur(9))
    dark = scene(brightness=18)
    busy = scene(busy_bottom=True)

    s_sharp = covers.frame_scores(sharp)
    s_blur = covers.frame_scores(blurred)
    s_dark = covers.frame_scores(dark)
    s_busy = covers.frame_scores(busy)

    check("sharp frame scores higher than a blurred one", s_sharp["score"] > s_blur["score"],
          f'{s_sharp["score"]} vs {s_blur["score"]}')
    check("blur is visible in the breakdown", s_sharp["breakdown"]["sharpness"] > s_blur["breakdown"]["sharpness"])
    check("a near-black frame loses exposure points", s_dark["breakdown"]["exposure"] < s_sharp["breakdown"]["exposure"])
    check("a busy lower third loses negative space",
          s_busy["breakdown"]["negative_space"] < s_sharp["breakdown"]["negative_space"],
          f'{s_busy["breakdown"]["negative_space"]} vs {s_sharp["breakdown"]["negative_space"]}')
    check("scores stay inside 0-100", all(0 <= v["score"] <= 100 for v in (s_sharp, s_blur, s_dark, s_busy)))

    ranked = covers.rank_frames([(12.0, blurred), (4.0, sharp), (8.0, dark)])
    check("ranking puts the best frame first", ranked[0]["time"] == 4.0, str([r["time"] for r in ranked]))
    again = covers.rank_frames([(12.0, blurred), (4.0, sharp), (8.0, dark)])
    check("ranking is deterministic", [r["time"] for r in ranked] == [r["time"] for r in again])
    check("candidate times avoid the exact clip edges",
          covers.candidate_times(10, 40, 5)[0] > 10 and covers.candidate_times(10, 40, 5)[-1] < 40)

    # Headlines
    good = covers.score_headline("The day the company nearly died")
    bait = covers.score_headline("SHOCKING: you won't believe what happened")
    long = covers.score_headline("This is a very long headline that keeps going far past what a cover can hold")
    check("a concrete, short line scores well", good["score"] >= 70, str(good))
    check("clickbait is penalised", bait["score"] < good["score"], str(bait))
    check("an overlong line is penalised", long["score"] < good["score"], str(long))
    check("cleaning removes hashtags, quotes and emoji",
          covers.clean_headline('#AI "changed" everything 🔥') == "AI changed everything",
          covers.clean_headline('#AI "changed" everything 🔥'))
    picked = covers.choose_headline(["SHOCKING: you won't believe this",
                                     "The day the company nearly died"])
    check("the strongest headline wins", picked["headline"] == "The day the company nearly died", str(picked))
    check("headline options are offered", len(picked["options"]) >= 1)

    # Composition
    tmp = Path(tempfile.mkdtemp())
    brand = {"tokens": normalize_tokens({"name": "Northwind", "accent": "#12AB34",
                                         "typography": {"heading": "playfair", "caption": "archivo"}})}
    headline = "The day the company nearly died"
    for comp in covers.COMPOSITIONS:
        made = covers.render_cover(scene(), tmp / f"{comp}.jpg", headline, comp, brand, "editorial")
        check(f"{comp} cover is written", Path(made["path"]).is_file() and Path(made["path"]).stat().st_size > 5000)
        img = Image.open(made["path"])
        check(f"{comp} cover is 1080x1920", img.size == (1080, 1920), str(img.size))
        check(f"{comp} cover reports no overflow", made["overflow"] is False, str(made))
        x0, y0, x1, y1 = made["text_box"]
        check(f"{comp} text box stays on the canvas", 0 <= x0 < x1 <= 1080 and 0 <= y0 < y1 <= 1920,
              str(made["text_box"]))
        font = covers._font("playfair" if comp in ("editorial", "documentary", "minimal") else "archivo",
                            made["font_size"])
        widest = max(covers._measure(ImageDraw.Draw(img), line, font) for line in made["lines"])
        check(f"{comp} lines fit the promised width", widest <= (x1 - x0) + 2,
              f"{widest} > {x1 - x0}")
        check(f"{comp} keeps the brand accent", made["brand_accent"] == "#12AB34")

    # The accent actually reaches the pixels.
    made = covers.render_cover(scene(), tmp / "accent.jpg", headline, "statement", brand, "statement")
    img = Image.open(made["path"]).convert("RGB")
    hits = sum(1 for px in img.getdata()
               if max(abs(px[i] - (18, 171, 52)[i]) for i in range(3)) <= 14)
    check("brand accent is drawn into the cover", hits > 100, str(hits))

    # Long words shrink instead of spilling out.
    tight = covers.render_cover(scene(), tmp / "tight.jpg", "Extraordinarily Uncompromising Internationalisation",
                                "statement", brand, "statement")
    check("a single long word is shrunk, not clipped", tight["overflow"] is False, str(tight))

    # Planning follows the direction and the Brand Kit.
    clip = {"hook": "We ran out of money in three weeks.",
            "title": "The week the runway ended", "topic": "Founders",
            "narrative_summary": "A founder describes the week the company almost closed."}
    plan = covers.plan(clip, brand, "minimalist")
    check("plan chooses the minimalist composition", plan["composition"] == "minimal", str(plan))
    check("plan keeps the headline short", len(plan["headline"].split()) <= 8, plan["headline"])
    fixed = {"tokens": normalize_tokens({**DEFAULT_TOKENS, "name": "X", "cover": {"composition": "kinetic"}})}
    check("an explicit brand composition wins", covers.plan(clip, fixed, "minimalist")["composition"] == "kinetic")

    if fails:
        print(f"\n{len(fails)} failed: " + ", ".join(fails))
        sys.exit(1)
    print("\nAll cover tests passed!")


if __name__ == "__main__":
    main()
