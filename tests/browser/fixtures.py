"""Isolated browser-test server and a reproducible finished project.

The server runs on a free port against a temporary data folder. Nothing here touches the user's real
data folder, their running server, or an AI provider. A small VP8/Opus clip is generated with the project's
FFmpeg so the studio has a real playable video, cover and word timings to render.
"""
from __future__ import annotations

import json
import math
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
import wave
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
JID = "20260101-120000-browsertest"
CID = "c1"


def ffmpeg_dir() -> Path | None:
    found = shutil.which("ffmpeg")
    if found:
        return Path(found).parent
    for candidate in sorted((ROOT / ".tools" / "ffmpeg").glob("*/bin")):
        if (candidate / "ffmpeg.exe").is_file() or (candidate / "ffmpeg").is_file():
            return candidate
    return None


def _run(cmd: list[str]) -> None:
    subprocess.run(cmd, check=True, capture_output=True, timeout=120)


def make_clip(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    ffmpeg = str((ffmpeg_dir() or Path(".")) / ("ffmpeg.exe" if os.name == "nt" else "ffmpeg"))
    _run([ffmpeg, "-y", "-v", "error",
          "-f", "lavfi", "-i", "testsrc2=size=540x960:rate=30",
          "-f", "lavfi", "-i", "sine=frequency=220:sample_rate=48000",
          "-t", "6", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-b:v", "450k",
          "-c:a", "aac", "-b:a", "64k", "-movflags", "+faststart", str(path)])


def make_cover(path: Path) -> None:
    from PIL import Image, ImageDraw
    img = Image.new("RGB", (1080, 1920), (26, 28, 31))
    draw = ImageDraw.Draw(img)
    draw.rectangle((0, 1320, 1080, 1920), fill=(197, 138, 76))
    draw.text((90, 720), "BUILD\nSOMETHING\nREAL", fill=(245, 242, 234))
    img.save(path, "JPEG", quality=88)


def make_wav(path: Path) -> None:
    with wave.open(str(path), "w") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(48000)
        frames = bytearray()
        for i in range(24000):
            value = int(9000 * math.sin(2 * math.pi * 440 * i / 48000))
            frames += value.to_bytes(2, "little", signed=True)
        w.writeframes(bytes(frames))


def seed_project(data: Path) -> tuple[str, str]:
    job_dir = data / "users" / "u_local" / "jobs" / JID
    clips = job_dir / "clips"
    clips.mkdir(parents=True, exist_ok=True)
    make_clip(clips / "c1.mp4")
    # The clean cut the Caption Studio previews on (no burned-in captions in this fixture).
    shutil.copyfile(clips / "c1.mp4", clips / "c1.src.mp4")
    make_cover(clips / "c1_cover.jpg")
    words = [{"w": word, "s": round(0.4 + i * 0.38, 2), "e": round(0.75 + i * 0.38, 2)}
             for i, word in enumerate("This is what it sounds like when a thought lands".split())]
    (job_dir / "words.json").write_text(json.dumps(words), encoding="utf-8")
    now = time.time()
    clip = {
        "id": CID, "start": 0.0, "end": 6.0, "score": 88, "confidence": 0.82,
        "approval_status": "recommended", "status": "done",
        "title": "A thought that lands in one piece",
        "hook": "BUILD SOMETHING REAL",
        "description": "A short excerpt about finishing what you start.",
        "creative_direction": "editorial", "style": "bounce", "layout": "blur",
        "captions": True, "branding": True, "watermark": False, "intro_cover": False, "outro": True,
        "file": "c1.mp4", "cover": "c1_cover.jpg", "reel_cover": "c1_cover.jpg",
        "src": str(clips / "c1.src.mp4"),
        "made_at": now, "quality_check": {"ok": True}, "quality": {"ok": True},
        "brand_name": "Studio", "ig_handle": "studio", "yt_channel": "studio", "brand_color": "#D99045",
        "instagram": {"hook": "The sentence that changes the room.",
                      "caption": "Some thoughts only land when you stop editing them.",
                      "hashtags": ["podcast", "clips", "creative"]},
        "youtube": {"title": "The sentence that changes the room",
                    "description": "A short excerpt about finishing what you start.",
                    "hashtags": ["podcast", "clips", "creative"]},
    }
    job = {
        "id": JID, "title": "The Long Conversation", "kind": "video", "creator": None,
        "source_path": str(clips / "c1.mp4"),
        "status": "done", "stage": "Finished", "progress": 100, "error": None,
        "created": now - 300, "updated": now - 60, "duration": 6.0,
        "width": 1080, "height": 1920, "uploader": "Browser Fixture",
        "source": {"type": "file", "name": "episode.mp4", "size": 120000},
        "options": {
            "max_clips": 8, "min_len": 15, "max_len": 60, "style": "bounce", "layout": "blur",
            "quality": 720, "range_start": None, "range_end": None, "captions": True,
            "hook_text": "", "description_text": "", "mode": "podcast", "duration_mode": "content",
            "direction": "auto", "branding": None, "watermark": None, "intro_cover": False,
            "outro": True, "brand_name": "Studio", "ig_handle": "studio", "yt_channel": "studio",
            "brand_color": "#D99045", "brand_id": "",
        },
        "clips": [clip],
        "ai": {"tokens": 0, "note": "fixture", "model": ""},
    }
    (job_dir / "job.json").write_text(json.dumps(job, indent=1), encoding="utf-8")
    return JID, CID


class StudioServer:
    """A real Clipsora server with an empty database and one seeded project."""

    def __init__(self) -> None:
        self.data = Path(tempfile.mkdtemp(prefix="clipsora-browser-"))
        self.port = _free_port()
        self.base = f"http://127.0.0.1:{self.port}"
        self.jid, self.cid = seed_project(self.data)
        self.proc: subprocess.Popen | None = None
        self.log = self.data / "server.log"

    def start(self) -> "StudioServer":
        env = {**os.environ,
               "CLIPSORA_DATA": str(self.data), "CLIPSORA_PORT": str(self.port),
               "CLIPSORA_PUBLIC_URL": self.base, "CLIPSORA_HOST": "127.0.0.1",
               "CLIPSORA_AUTO_RELOAD": "0", "CLIPSORA_UPDATE_CHECK": "0",
               "CLIPSORA_ACCOUNTS": "0", "CLIPSORA_FETCH_MODEL": "0", "DATABASE_URL": "",
               "CLIPSORA_AI_KEY": "", "CLIPSORA_AI_KEY_FILE": "", "CLIPSORA_SMTP_HOST": "",
               "GOOGLE_CLIENT_ID": "", "GOOGLE_CLIENT_SECRET": "", "GOOGLE_CLIENT_FILE": "",
               "CLIPSORA_MAX_UPLOAD_MB": "32", "PYTHONUNBUFFERED": "1"}
        d = ffmpeg_dir()
        if d:
            env["PATH"] = str(d) + os.pathsep + env.get("PATH", "")
        with self.log.open("w", encoding="utf-8") as out:
            self.proc = subprocess.Popen([sys.executable, "-m", "studio.server"], cwd=ROOT,
                                         env=env, stdout=out, stderr=subprocess.STDOUT)
        deadline = time.time() + 90
        while time.time() < deadline:
            if self.proc.poll() is not None:
                raise RuntimeError("The browser-test server stopped:\n" + self.log.read_text(errors="replace")[-3000:])
            try:
                urllib.request.urlopen(self.base + "/healthz", timeout=2)
                return self
            except Exception:
                time.sleep(0.4)
        self.stop()
        raise RuntimeError("The browser-test server did not start:\n" + self.log.read_text(errors="replace")[-3000:])

    def stop(self) -> None:
        try:
            if self.log.is_file():
                target = ROOT / "tests" / "browser" / "artifacts" / "server-last.log"
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(self.log, target)
            errors = list((self.data / "users").glob("*/jobs/*/error.log"))
            if errors:
                shutil.copyfile(errors[0], ROOT / "tests" / "browser" / "artifacts" / "render-error.log")
        except OSError:
            pass
        if self.proc and self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=15)
            except subprocess.TimeoutExpired:
                self.proc.kill()
        shutil.rmtree(self.data, ignore_errors=True)

    def __enter__(self):
        return self.start()

    def __exit__(self, *exc):
        self.stop()


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])
