"""Brand look for finished Shorts: reel covers, a moving logo during the clip, and a 2-second follow-up card.

The colours and fonts follow the brand sheet:
- Charcoal #111214, Off-White #F4F2ED, Orange #F47B20, Grey #858585
- Headlines on covers: Anton (tall, narrow capitals like the sheet's covers)
- Tagline: Playfair Display Italic. Small text: Montserrat SemiBold.

If the person uploaded their own logo (a PNG), it is used everywhere. Otherwise a drawn stand-in of the
V-and-microphone icon is used. Every font here is under the SIL Open Font License; see CREDITS.md.
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path
from typing import List, Optional

from PIL import Image, ImageDraw, ImageEnhance, ImageFont, ImageFilter

from . import config

# --- Brand colours ---
CHARCOAL = (17, 18, 20)          # #111214
OFF_WHITE = (244, 242, 237)      # #F4F2ED
ORANGE = (244, 123, 32)          # #F47B20
GREY = (133, 133, 133)           # #858585
RED_YT = (255, 0, 0)

NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
FONT_FILES = {
    "poppins": "Poppins-ExtraBold.ttf",
    "archivo": "ArchivoBlack-Regular.ttf",
    "anton": "Anton-Regular.ttf",
    "montserrat": "Montserrat-SemiBold.ttf",
    "playfair": "PlayfairDisplay-Italic.ttf",
    "bebas": "BebasNeue-Regular.ttf",
    "fjalla": "FjallaOne-Regular.ttf",
    "dmserif": "DMSerifDisplay-Regular.ttf",
    "zilla": "ZillaSlab-SemiBold.ttf",
    "bungee": "Bungee-Regular.ttf",
    "russo": "RussoOne-Regular.ttf",
    "marker": "PermanentMarker-Regular.ttf",
    "mono": "SpaceMono-Regular.ttf",
}


def _get_font(font_name: str = "poppins", size: int = 40):
    """A bundled font at this size. Falls back to the next bundled font, then Pillow's own."""
    order = [font_name.lower(), "poppins"]
    for name in order:
        fname = FONT_FILES.get(name)
        if not fname:
            continue
        for p in (Path(__file__).parent / "fonts" / fname, config.FONTS_DIR / fname):
            if p.is_file():
                try:
                    return ImageFont.truetype(str(p), size)
                except Exception:  # noqa: BLE001 - a broken font file must not stop a render
                    pass
    return ImageFont.load_default()


def _text_w(font, text: str) -> int:
    try:
        b = font.getbbox(text)
        return b[2] - b[0]
    except Exception:  # noqa: BLE001
        return len(text) * 20


def draw_viral_mic_icon(draw: ImageDraw.ImageDraw, x: int, y: int, size: int = 60, accent_color=ORANGE, white_color=OFF_WHITE):
    """The drawn stand-in for the logo: mathematically perfected V and studio broadcast microphone."""
    s = size / 256.0
    # Left Arm of V (Pure White)
    draw.polygon([(x + 28.0 * s, y + 44.7 * s), (x + 82.0 * s, y + 44.7 * s),
                  (x + 128.0 * s, y + 124.4 * s), (x + 128.0 * s, y + 217.9 * s)],
                 fill=white_color)
    # Right Arm of V (Electric Orange)
    draw.polygon([(x + 228.0 * s, y + 44.7 * s), (x + 174.0 * s, y + 44.7 * s),
                  (x + 128.0 * s, y + 124.4 * s), (x + 128.0 * s, y + 217.9 * s)],
                 fill=accent_color)
    # Microphone capsule dome and body
    draw.rounded_rectangle([x + 103.0 * s, y + 38.1 * s, x + 153.0 * s, y + 91.9 * s], radius=int(25.0 * s), fill=accent_color)
    # Triangular base
    draw.polygon([(x + 109.2 * s, y + 91.9 * s), (x + 146.8 * s, y + 91.9 * s), (x + 128.0 * s, y + 124.4 * s)], fill=accent_color)
    # Slits
    for sy, sw in [(48.0, 38.0), (59.0, 42.0), (70.0, 42.0), (81.0, 38.0)]:
        sx = x + 128.0 * s - (sw * s) / 2.0
        draw.rounded_rectangle([sx, y + sy * s, sx + sw * s, y + (sy + 4.5) * s], radius=max(1, int(2.2 * s)), fill=CHARCOAL)


def _default_brand_asset(brand_name: str = "") -> Optional[Path]:
    """Return bundled raster logo only when the configured brand matches it, never leaking onto other brands."""
    norm = re.sub(r"[^a-z0-9]", "", (brand_name or "").lower())
    if norm == "viralmic":
        p = Path(__file__).parent / "assets" / "viralmic_profile.png"
        if p.is_file():
            return p
    return None


def logo_icon(size: int, logo_path: Optional[Path | str] = None, brand_name: str = "") -> Image.Image:
    """A square see-through picture of the logo: uploaded raster file or matching brand asset, else drawn icon."""
    target_path = Path(logo_path) if logo_path else None
    if not target_path or not target_path.is_file():
        target_path = _default_brand_asset(brand_name)

    if target_path and target_path.is_file() and target_path.suffix.lower() != ".svg":
        try:
            img = Image.open(target_path).convert("RGBA")
            img.thumbnail((size, size), Image.Resampling.LANCZOS)
            out = Image.new("RGBA", (size, size), (0, 0, 0, 0))
            out.paste(img, ((size - img.width) // 2, (size - img.height) // 2), img)
            return out
        except Exception:  # noqa: BLE001 - an unreadable upload falls back to drawn icon
            pass

    out = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw_viral_mic_icon(ImageDraw.Draw(out), 0, 0, size=size)
    return out


def _brand_word(draw, x, y, brand: str, font):
    """Writes the brand name the way the sheet does: the first part light, the last three letters orange
    (VIRAL + MIC). Short names are written all in the light colour."""
    brand = brand.upper()
    head, tail = (brand[:-3], brand[-3:]) if len(brand) > 5 else (brand, "")
    draw.text((x, y), head, fill=OFF_WHITE, font=font)
    if tail:
        draw.text((x + _text_w(font, head), y), tail, fill=ORANGE, font=font)
    return _text_w(font, brand)


def create_brand_watermark_image(brand_name: str = "", width: int = 320, height: int = 80,
                                 accent_color=ORANGE, white_color=OFF_WHITE, logo_path=None) -> Image.Image:
    """The small logo shown in the corner while the clip plays: icon plus name, on a see-through background."""
    brand_name = brand_name or config.BRAND_NAME or "STUDIO"
    img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    icon = int(height * 0.8)
    img.alpha_composite(logo_icon(icon, logo_path, brand_name), (8, (height - icon) // 2))
    font = _get_font("archivo", int(height * 0.42))
    _brand_word(ImageDraw.Draw(img), icon + 18, int(height * 0.26), brand_name, font)
    return img


def _headline_lines(text: str) -> List[str]:
    words = re.sub(r"\s+", " ", str(text or "").strip().upper()).split()[:7] or ["THE", "NEXT", "FRONTIER"]
    if len(words) <= 3:
        return words
    if len(words) == 4:
        return [" ".join(words[:2]), " ".join(words[2:])]
    a = max(1, len(words) // 3)
    b = max(a + 1, (2 * len(words)) // 3)
    return [" ".join(words[:a]), " ".join(words[a:b]), " ".join(words[b:])]


def create_reel_cover(video_path: Path | str, output_path: Path | str, headline: str, timestamp: float = 1.0,
                      brand_name: str = "", width: int = 1080, height: int = 1920, logo_path=None) -> Path:
    """A 9:16 cover like the sheet's: a frame from the clip, a dark fade at the bottom, a tall headline in
    light and orange lines, a short orange rule, and the logo with the brand name at the foot."""
    brand_name = brand_name or config.BRAND_NAME or "STUDIO"
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    vp = Path(video_path)
    if vp.is_file() and vp.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp"):
        base = Image.open(vp).convert("RGB")
    else:
        frame = output_path.parent / f"_frame_{output_path.stem}.jpg"
        try:
            subprocess.run(["ffmpeg", "-y", "-v", "error", "-ss", f"{max(0.0, timestamp):.2f}", "-i", str(vp),
                            "-frames:v", "1", "-q:v", "2", str(frame)],
                           capture_output=True, text=True, creationflags=NO_WINDOW, timeout=30)
        except Exception:  # noqa: BLE001
            pass
        if frame.is_file():
            base = Image.open(frame).convert("RGB")
            frame.unlink(missing_ok=True)
        else:
            base = Image.new("RGB", (width, height), CHARCOAL)

    # fill the 9:16 frame, cropping whatever does not fit
    w, h = base.size
    if w / h > width / height:
        nw = int(h * width / height)
        base = base.crop(((w - nw) // 2, 0, (w - nw) // 2 + nw, h))
    else:
        nh = int(w * height / width)
        base = base.crop((0, (h - nh) // 2, w, (h - nh) // 2 + nh))
    base = ImageEnhance.Contrast(base.resize((width, height), Image.Resampling.LANCZOS)).enhance(1.1)

    shade = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    sd = ImageDraw.Draw(shade)
    top = int(height * 0.40)
    for y in range(top, height):
        sd.line([(0, y), (width, y)], fill=CHARCOAL + (int(245 * ((y - top) / (height - top)) ** 1.3),))
    cover = Image.alpha_composite(base.convert("RGBA"), shade)
    draw = ImageDraw.Draw(cover)

    lines = _headline_lines(headline)
    left = int(width * 0.08)
    size = int(width * 0.15)
    font = _get_font("anton", size)
    while size > 60 and max(_text_w(font, ln) for ln in lines) > width - 2 * left:   # long words: shrink to fit
        size -= 6
        font = _get_font("anton", size)
    step = int(size * 1.02)
    bottom = height - int(height * 0.25)
    y0 = bottom - step * len(lines)
    for i, ln in enumerate(lines):
        # as on the sheet: first line light, the rest orange ("THE / NEXT FRONTIER", "PEACE / OR WAR?")
        colour = OFF_WHITE if (i == 0 and len(lines) > 1) or len(lines) == 1 else ORANGE
        draw.text((left + 3, y0 + i * step + 3), ln, fill=(0, 0, 0, 200), font=font)
        draw.text((left, y0 + i * step), ln, fill=colour, font=font)
    draw.rectangle([left, bottom + 18, left + int(width * 0.09), bottom + 26], fill=ORANGE)

    icon = int(width * 0.05)
    small = _get_font("archivo", int(width * 0.034))
    total = icon + 14 + _text_w(small, brand_name.upper())
    fx, fy = (width - total) // 2, height - int(height * 0.16)
    cover.alpha_composite(logo_icon(icon, logo_path, brand_name), (fx, fy - icon // 6))
    _brand_word(draw, fx + icon + 14, fy, brand_name, small)

    cover.convert("RGB").save(str(output_path), "JPEG", quality=94, optimize=True)
    return output_path


def _outro_card(width: int, height: int, brand_name: str, ig_handle: str, yt_channel: str, tagline: str,
                logo_path: Optional[str] = None, cta: str = "") -> Image.Image:
    """A cinematic, luxury dark outro card with radial spotlight, authentic badge, and frosted glass social buttons."""
    card = Image.new("RGBA", (width, height), (10, 11, 14, 255))

    # Ambient radial spotlight in upper center
    glow = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    cx, cy = width // 2, int(height * 0.28)
    for r in range(int(width * 0.44), 0, -12):
        alpha = int(45 * (1.0 - (r / (width * 0.44))) ** 1.6)
        gd.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(244, 123, 32, alpha))
    card = Image.alpha_composite(card, glow)
    draw = ImageDraw.Draw(card)

    # Top Kicker
    f_kicker = _get_font("montserrat", int(width * 0.021))
    kicker = "JOIN THE CONVERSATION"
    kw = _text_w(f_kicker, kicker)
    draw.text(((width - kw) // 2, int(height * 0.08)), kicker, fill=GREY, font=f_kicker)

    # Brand Emblem / Badge
    badge_size = int(width * 0.38)
    by = int(height * 0.13)
    bx = (width - badge_size) // 2

    target_logo = Path(logo_path) if logo_path else None
    if not target_logo or not target_logo.is_file():
        target_logo = _default_brand_asset(brand_name)

    if target_logo and target_logo.is_file() and target_logo.suffix.lower() != ".svg":
        try:
            b_img = Image.open(target_logo).convert("RGBA").resize((badge_size, badge_size), Image.Resampling.LANCZOS)
            # Circular mask with smooth anti-aliasing
            mask = Image.new("L", (badge_size, badge_size), 0)
            md = ImageDraw.Draw(mask)
            md.ellipse([0, 0, badge_size, badge_size], fill=255)

            # Soft shadow behind badge
            sh_size = badge_size + 40
            shadow = Image.new("RGBA", (sh_size, sh_size), (0, 0, 0, 0))
            sd = ImageDraw.Draw(shadow)
            sd.ellipse([20, 20, sh_size - 20, sh_size - 20], fill=(0, 0, 0, 180))
            shadow = shadow.filter(ImageFilter.GaussianBlur(14))
            card.alpha_composite(shadow, (bx - 20, by - 10))
            card.paste(b_img, (bx, by), mask)
        except Exception:
            card.alpha_composite(logo_icon(badge_size, logo_path, brand_name), (bx, by))
    else:
        card.alpha_composite(logo_icon(badge_size, logo_path, brand_name), (bx, by))

    # Brand Name Wordmark (dynamic from brand_name)
    ty = by + badge_size + int(height * 0.035)
    f_title = _get_font("archivo", int(width * 0.082))
    display_brand = (brand_name or config.BRAND_NAME or "STUDIO").upper()
    total_w = _text_w(f_title, display_brand)
    tx = (width - total_w) // 2
    _brand_word(draw, tx, ty, display_brand, f_title)

    # Dual-Line Tagline (uses tagline parameter dynamically)
    f_tag = _get_font("playfair", int(width * 0.046))
    tgy1 = ty + int(height * 0.062)
    raw_tag = (tagline or "Big Conversations. Powerful Perspectives.").strip()
    if ". " in raw_tag:
        part1, _, part2 = raw_tag.partition(". ")
        tag1, tag2 = part1 + ".", part2
    else:
        tag1, tag2 = raw_tag, ""
    tw1 = _text_w(f_tag, tag1)
    draw.text(((width - tw1) // 2, tgy1), tag1, fill=OFF_WHITE, font=f_tag)
    tgy2 = tgy1 + int(height * 0.034)
    if tag2:
        tw2 = _text_w(f_tag, tag2)
        draw.text(((width - tw2) // 2, tgy2), tag2, fill=ORANGE, font=f_tag)

    # Glowing orange divider rule
    rule_y = (tgy2 if tag2 else tgy1) + int(height * 0.045)
    rule_w = int(width * 0.24)
    draw.rounded_rectangle([(width - rule_w) // 2, rule_y, (width + rule_w) // 2, rule_y + 4], radius=2, fill=ORANGE)

    # Social Call-to-Action Cards (Frosted Glass)
    bw, bh = int(width * 0.86), int(height * 0.076)
    bx = (width - bw) // 2
    start_y = rule_y + int(height * 0.04)

    f_sub = _get_font("montserrat", int(width * 0.022))
    f_handle = _get_font("montserrat", int(width * 0.038))
    f_btn = _get_font("montserrat", int(width * 0.028))
    icon_s = int(bh * 0.62)
    btn_h = int(bh * 0.52)
    ix = bx + int(bh * 0.24)

    # 1. Instagram Card
    if ig_handle:
        pill1 = Image.new("RGBA", (bw, bh), (0, 0, 0, 0))
        pd1 = ImageDraw.Draw(pill1)
        pd1.rounded_rectangle([0, 0, bw, bh], radius=bh // 3, fill=(20, 22, 28, 235), outline=(55, 58, 70, 220), width=2)
        card.alpha_composite(pill1, (bx, start_y))

        # Original Instagram Logo
        iy = start_y + (bh - icon_s) // 2
        ig_file = Path(__file__).parent / "assets" / "instagram_official.png"
        if ig_file.is_file():
            try:
                ig_img = Image.open(ig_file).convert("RGBA").resize((icon_s, icon_s), Image.Resampling.LANCZOS)
                card.alpha_composite(ig_img, (ix, iy))
            except Exception:
                ig_file = None
        if not ig_file or not ig_file.is_file():
            ig_icon = Image.new("RGBA", (icon_s, icon_s), (0, 0, 0, 0))
            igd = ImageDraw.Draw(ig_icon)
            igd.rounded_rectangle([0, 0, icon_s, icon_s], radius=int(icon_s * 0.28), fill=(225, 48, 108, 255))
            igd.rounded_rectangle([int(icon_s * 0.16), int(icon_s * 0.16), int(icon_s * 0.84), int(icon_s * 0.84)], radius=int(icon_s * 0.22), outline=OFF_WHITE, width=3)
            igd.ellipse([int(icon_s * 0.34), int(icon_s * 0.34), int(icon_s * 0.66), int(icon_s * 0.66)], outline=OFF_WHITE, width=3)
            igd.ellipse([int(icon_s * 0.68), int(icon_s * 0.24), int(icon_s * 0.76), int(icon_s * 0.32)], fill=OFF_WHITE)
            card.alpha_composite(ig_icon, (ix, iy))

        tx_text = ix + icon_s + int(width * 0.03)
        draw.text((tx_text, start_y + int(bh * 0.22)), "FOLLOW FOR DAILY CLIPS", fill=GREY, font=f_sub)
        draw.text((tx_text, start_y + int(bh * 0.44)), f"@{ig_handle.lstrip('@')}", fill=OFF_WHITE, font=f_handle)

        # "Follow" action button
        btn_w = int(width * 0.18)
        btn_x = bx + bw - btn_w - int(bh * 0.24)
        btn_y = start_y + (bh - btn_h) // 2
        draw.rounded_rectangle([btn_x, btn_y, btn_x + btn_w, btn_y + btn_h], radius=btn_h // 2, fill=ORANGE)
        btw = _text_w(f_btn, "Follow")
        draw.text((btn_x + (btn_w - btw) // 2, btn_y + (btn_h - int(width * 0.028)) // 2 - 2), "Follow", fill=(255, 255, 255), font=f_btn)

    # 2. YouTube Card
    if yt_channel:
        start_y2 = (start_y + bh + int(height * 0.022)) if ig_handle else start_y
        pill2 = Image.new("RGBA", (bw, bh), (0, 0, 0, 0))
        pd2 = ImageDraw.Draw(pill2)
        pd2.rounded_rectangle([0, 0, bw, bh], radius=bh // 3, fill=(20, 22, 28, 235), outline=(55, 58, 70, 220), width=2)
        card.alpha_composite(pill2, (bx, start_y2))

        # Original YouTube Red Logo
        iy2 = start_y2 + (bh - icon_s) // 2
        yt_file = Path(__file__).parent / "assets" / "youtube_official.png"
        if yt_file.is_file():
            try:
                yt_img = Image.open(yt_file).convert("RGBA").resize((icon_s, icon_s), Image.Resampling.LANCZOS)
                card.alpha_composite(yt_img, (ix, iy2))
            except Exception:
                yt_file = None
        if not yt_file or not yt_file.is_file():
            yt_icon = Image.new("RGBA", (icon_s, icon_s), (0, 0, 0, 0))
            ytd = ImageDraw.Draw(yt_icon)
            ytd.rounded_rectangle([0, int(icon_s * 0.12), icon_s, int(icon_s * 0.88)], radius=int(icon_s * 0.22), fill=RED_YT)
            ytd.polygon([(int(icon_s * 0.38), int(icon_s * 0.32)), (int(icon_s * 0.72), int(icon_s * 0.50)), (int(icon_s * 0.38), int(icon_s * 0.68))], fill=OFF_WHITE)
            card.alpha_composite(yt_icon, (ix, iy2))

        tx_text = ix + icon_s + int(width * 0.03)
        draw.text((tx_text, start_y2 + int(bh * 0.22)), "SUBSCRIBE FOR FULL EPISODES", fill=GREY, font=f_sub)
        clean_yt = yt_channel if yt_channel.startswith("@") else f"@{yt_channel.lstrip('/')}"
        draw.text((tx_text, start_y2 + int(bh * 0.44)), clean_yt, fill=OFF_WHITE, font=f_handle)

        # "Subscribe" action button
        btn_w2 = int(width * 0.22)
        btn_x2 = bx + bw - btn_w2 - int(bh * 0.24)
        draw.rounded_rectangle([btn_x2, start_y2 + (bh - btn_h) // 2, btn_x2 + btn_w2, start_y2 + (bh - btn_h) // 2 + btn_h], radius=btn_h // 2, fill=RED_YT)
        btw2 = _text_w(f_btn, "Subscribe")
        draw.text((btn_x2 + (btn_w2 - btw2) // 2, start_y2 + (bh - btn_h) // 2 + (btn_h - int(width * 0.028)) // 2 - 2), "Subscribe", fill=(255, 255, 255), font=f_btn)

    # One primary action from the Brand Kit, above the signature.
    if cta:
        f_cta = _get_font("montserrat", int(width * 0.022))
        line = str(cta)[:70]
        cw = _text_w(f_cta, line)
        draw.text(((width - cw) // 2, int(height * 0.805)), line, fill=OFF_WHITE, font=f_cta)

    # Footer Signature (kept inside bottom safe zone at 84%)
    f_foot = _get_font("montserrat", int(width * 0.019))
    foot_text = f"{display_brand} MEDIA" if display_brand else ""
    if foot_text:
        ftw = _text_w(f_foot, foot_text)
        draw.text(((width - ftw) // 2, int(height * 0.84)), foot_text, fill=(75, 78, 90), font=f_foot)

    return card


def render_outro_card(output_path: Path | str, brand_name: str = "", ig_handle: str = "",
                      yt_channel: str = "", duration: float = 2.0, width: int = 1080, height: int = 1920,
                      fps: int = 30, tagline: str = "Big Conversations. Powerful Perspectives.", logo_path=None,
                      cta: str = "") -> Path:
    """The 2-second end card asking viewers to follow on Instagram and YouTube. It fades up from black and
    pushes in very slightly, so it feels alive rather than a still picture. Silent sound track included, so it
    can be joined onto any clip."""
    brand_name = brand_name or config.BRAND_NAME or "STUDIO"
    ig_handle = ig_handle or config.IG_HANDLE
    yt_channel = yt_channel or config.YT_CHANNEL
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    png = output_path.parent / f"_card_{output_path.stem}.png"
    _outro_card(width, height, brand_name, ig_handle, yt_channel, tagline, logo_path, cta).convert("RGB").save(png)
    frames = max(1, int(round(duration * fps)))
    push = (f"zoompan=z='1+0.035*on/{frames}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':"
            f"d={frames}:s={width}x{height}:fps={fps}")
    try:
        p = subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(png),
                            "-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo",
                            "-vf", f"{push},fade=t=in:st=0:d=0.3,format=yuv420p",
                            "-t", f"{duration:.2f}", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
                            "-c:a", "aac", "-b:a", "160k", "-ar", "48000", "-shortest", str(output_path)],
                           capture_output=True, text=True, creationflags=NO_WINDOW, timeout=90)
        if p.returncode != 0:
            output_path.unlink(missing_ok=True)
            raise RuntimeError("Could not render the end card: " + p.stderr[-300:])
    finally:
        png.unlink(missing_ok=True)
    return output_path


def mix_signature_sound(video_path: Path | str, asset_path: Path | str, start_sec: float = 1.0,
                        spec: Optional[dict] = None) -> bool:
    """Lay the brand's audio logo over a finished clip. True when the mix was written.

    The original picture is copied, never re-encoded; the audio is replaced by the limited mix, so a failed
    sting cannot damage the clip and a successful one cannot clip the mix.
    """
    video_path, asset_path = Path(video_path), Path(asset_path)
    if not video_path.is_file() or not asset_path.is_file():
        return False
    from .brands import sonic_mix_filter
    out = video_path.with_name(video_path.stem + "_sonic.mp4")
    try:
        p = subprocess.run(
            ["ffmpeg", "-y", "-v", "error", "-i", str(video_path), "-i", str(asset_path),
             "-filter_complex", sonic_mix_filter(start_sec, spec or {}, 3600),
             "-map", "0:v", "-map", "[a]", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
             "-ar", "48000", "-movflags", "+faststart", str(out)],
            capture_output=True, text=True, creationflags=NO_WINDOW, timeout=300)
    except (OSError, subprocess.SubprocessError):
        out.unlink(missing_ok=True)
        return False
    if p.returncode != 0 or not out.is_file() or out.stat().st_size < 1000:
        out.unlink(missing_ok=True)
        return False
    out.replace(video_path)
    return True


def render_intro_cover_clip(cover_img_path: Path | str, output_path: Path | str, duration: float = 1.0,
                            width: int = 1080, height: int = 1920, fps: int = 30) -> Path:
    """Turn the 9:16 Reel Cover image into a crisp 1-second opening video with a subtle punch-in zoom and silent
    audio track, so it sits as frame 1 on Instagram/YouTube and transitions cleanly into the speaker."""
    cover_img_path, output_path = Path(cover_img_path), Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    frames = max(1, int(round(duration * fps)))
    push = (f"scale={width}:{height}:force_original_aspect_ratio=increase,crop={width}:{height},"
            f"zoompan=z='1+0.03*on/{frames}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':"
            f"d={frames}:s={width}x{height}:fps={fps},format=yuv420p")
    p = subprocess.run(
        ["ffmpeg", "-y", "-v", "error", "-i", str(cover_img_path.resolve()),
         "-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo",
         "-vf", push, "-t", f"{duration:.2f}",
         "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
         "-c:a", "aac", "-b:a", "160k", "-ar", "48000", "-shortest", str(output_path)],
        capture_output=True, text=True, creationflags=NO_WINDOW, timeout=90,
    )
    if p.returncode != 0:
        output_path.unlink(missing_ok=True)
        raise RuntimeError("Could not build the 1-second cover intro: " + p.stderr[-300:])
    return output_path


def prepend_intro_to_clip(intro_path: Path | str, clip_path: Path | str, output_path: Path | str,
                          width: int = 1080, height: int = 1920, fps: int = 30) -> Path:
    """Prepend the 1-second cover intro before the clip while keeping the clip's audio and captions in lockstep."""
    intro_path, clip_path, output_path = Path(intro_path), Path(clip_path), Path(output_path)
    norm = f"scale={width}:{height}:force_original_aspect_ratio=decrease,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,fps={fps},setsar=1,format=yuv420p"
    snd = "aresample=48000,aformat=sample_fmts=fltp:channel_layouts=stereo"
    graph = (f"[0:v]{norm}[a];[1:v]{norm}[b];[0:a]{snd}[x];[1:a]{snd}[y];"
             f"[a][x][b][y]concat=n=2:v=1:a=1[v][o]")
    p = subprocess.run(
        ["ffmpeg", "-y", "-v", "error", "-i", str(intro_path.resolve()), "-i", clip_path.name,
         "-filter_complex", graph, "-map", "[v]", "-map", "[o]",
         "-c:v", "libx264", "-preset", "veryfast", "-crf", "21",
         "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", str(output_path.resolve())],
        cwd=str(clip_path.parent), capture_output=True, text=True, creationflags=NO_WINDOW, timeout=300,
    )
    if p.returncode != 0:
        output_path.unlink(missing_ok=True)
        raise RuntimeError("Could not prepend the 1-second cover intro: " + p.stderr[-300:])
    return output_path


def append_outro_to_clip(clip_path: Path | str, outro_path: Path | str, output_path: Path | str,
                         width: int = 1080, height: int = 1920, fps: int = 30) -> Path:
    """Joins the end card onto the clip. Both are brought to the same size, frame rate and sound format first,
    so the join never stutters or drifts, and the clip's sound fades out over its last quarter second."""
    clip_path, outro_path, output_path = Path(clip_path), Path(outro_path), Path(output_path)
    norm = f"scale={width}:{height}:force_original_aspect_ratio=decrease,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,fps={fps},setsar=1,format=yuv420p"
    snd = "aresample=48000,aformat=sample_fmts=fltp:channel_layouts=stereo"
    clip_len = _duration(clip_path)
    fade = f",afade=t=out:st={max(0.0, clip_len - 0.25):.2f}:d=0.25" if clip_len else ""
    graph = (f"[0:v]{norm}[a];[1:v]{norm}[b];[0:a]{snd}{fade}[x];[1:a]{snd}[y];"
             f"[a][x][b][y]concat=n=2:v=1:a=1[v][o]")
    p = subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", clip_path.name, "-i", str(outro_path.resolve()),
                        "-filter_complex", graph, "-map", "[v]", "-map", "[o]",
                        "-c:v", "libx264", "-preset", "veryfast", "-crf", "21",
                        "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", str(output_path.resolve())],
                       cwd=str(clip_path.parent), capture_output=True, text=True, creationflags=NO_WINDOW, timeout=300)
    if p.returncode != 0:
        output_path.unlink(missing_ok=True)
        raise RuntimeError("Could not add the end card: " + p.stderr[-300:])
    return output_path


def _duration(path: Path) -> float:
    try:
        p = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=nw=1:nk=1",
                            str(path)], capture_output=True, text=True, creationflags=NO_WINDOW, timeout=30)
        return float(p.stdout.strip())
    except Exception:  # noqa: BLE001
        return 0.0


def build_animated_watermark_filter(logo_filename: str = "wm.png", start_sec: float = 1.0, end_sec: Optional[float] = None,
                                    scale_w: int = 240, margin_x: int = 36, margin_y: int = 48, position: str = "top_left",
                                    stream_in: Optional[str] = None, base_stream: str = "v0", out_stream: str = "v") -> str:
    """The filter that moves the corner logo: hidden for the first second (the opening line has the screen to
    itself), then it fades up and keeps a slow, gentle breathing glow (its strength rises and falls every three
    seconds). `stream_in` names an already-loaded looping picture; without it the picture file is opened here."""
    if position == "top_right":
        pos = f"W-w-{margin_x}:{margin_y}"
    elif position == "bottom_right":
        pos = f"W-w-{margin_x}:H-h-{margin_y}"
    else:
        pos = f"{margin_x}:{margin_y}"
    src = f"[{stream_in}]" if stream_in else f"movie={logo_filename},loop=-1:1,"
    breathe = "geq=r='r(X,Y)':g='g(X,Y)':b='b(X,Y)':a='alpha(X,Y)*(0.80+0.18*sin(2*PI*T/3))'"
    fade_out = (f",fade=t=out:st={max(start_sec, end_sec - 0.5):.2f}:d=0.5:alpha=1" if end_sec else "")
    return (f"{src}format=rgba,scale={scale_w}:-1,{breathe},"
            f"fade=t=in:st={start_sec:.2f}:d=0.6:alpha=1{fade_out}[logo];"
            f"[{base_stream}][logo]overlay={pos}:format=auto:shortest=1[{out_stream}]")
