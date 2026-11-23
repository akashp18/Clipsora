# Clipsora

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="web/brand/logo-light.svg">
  <img src="web/brand/logo.svg" alt="Clipsora" width="230">
</picture>

**A clipping studio that shows its work.** Your footage. Your AI. Your clips.

Clipsora turns long videos and live streams into captioned vertical clips, ready to post. Free and open source: run it on your own computer or server, with your own AI key.

Paste a YouTube, Twitch or Kick link (or upload a video file) and Clipsora finds the moments worth clipping, cuts them to 9:16 vertical format, adds word-by-word animated captions with a hook, and can schedule or post them to your connected accounts. It can also monitor a creator's live stream and extract highlight clips in real time while the stream is still running.

---

## Highlights

- **Clips from any video:** Transcribes audio locally on your machine, asks an AI model which moments hold attention, and renders vertical clips in your chosen frame and caption style.
- **Real-time live clipping:** Records a live stream into a rolling buffer and clips highlights as they happen using audio energy, chat activity, and transcripts.
- **14 caption styles & 16 frame layouts:** Clean, bold, editorial, karaoke, typewriter, and gamer styles, paired with blurred fills, split screens, facecam cuts, and brand canvases.
- **Built-in clip editor:** Trim start/end times, refine AI-generated hooks and titles, switch caption styles or frame layouts, and re-render only the clip you changed.
- **Creator workspaces:** Separate channel presets, clip defaults, posting rules, and logs for every creator you manage.
- **Multi-platform auto-posting:** Connect YouTube Shorts, Instagram Reels, and TikTok to queue or publish clips with rate limits and spacing.
- **Private & self-hosted:** No mandatory sign-in on your own computer. Audio stays on your machine; AI prompts send only transcripts without raw footage.
- **Bring your own AI (BYOK):** Works with Gemini, OpenAI, Grok, Groq, OpenRouter, Claude, local Ollama models, or loudness-only detection without any key.

---

## Quick Start

### Option A: Run with Docker (Recommended)

Make sure Docker Desktop (or the Docker daemon) is running.

1. **Clone the repository:**
   ```bash
   git clone https://github.com/akashp18/Clipsora.git
   cd Clipsora
   ```

2. **Build and run the container:**
   ```bash
   docker build -t clipsora .
   docker run -d --name clipsora -p 8765:8765 -v clipsora_data:/data clipsora
   ```

3. **Open the studio:**
   Visit [http://127.0.0.1:8765](http://127.0.0.1:8765). The dashboard opens directly without sign-in.

---

### Option B: Run locally with Python

**Requirements:**
- Python 3.10 or newer
- `ffmpeg` installed and available in your `PATH` (Windows: `winget install Gyan.FFmpeg`, macOS: `brew install ffmpeg`, Linux: `sudo apt install ffmpeg`)

> [!IMPORTANT]
> Install Clipsora in a short, permanent directory such as `C:\clipsora` on Windows or `~/clipsora` on macOS/Linux. On Windows, deeply nested paths can exceed the 260-character path limit and prevent the speech transcription library from loading.

1. **Clone and enter the directory:**
   ```bash
   git clone https://github.com/akashp18/Clipsora.git
   cd Clipsora
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Start the server:**
   ```bash
   python -m studio.server
   ```
   *On first launch, Clipsora downloads the local speech recognition model (~480 MB).*

4. **Open the studio:**
   Visit [http://127.0.0.1:8765](http://127.0.0.1:8765).

---

## Choose Your AI

Clipsora uses an AI chat model that outputs structured JSON to detect hooks and moments worth clipping. You bring your own API key and pay the provider directly:

1. In the dashboard, navigate to **Settings > AI**.
2. Select your provider, paste your API key, and click **Find models** to choose an available model.
3. Click **Save and test**. Keys are stored securely in your local data directory and never sent back to any third party.

Alternatively, configure your provider in a `.env` file (see [`.env.example`](.env.example)):

```ini
CLIPSORA_AI_PROVIDER=gemini
CLIPSORA_AI_MODELS=gemini-2.5-flash
CLIPSORA_AI_KEY=your-api-key-here
```

| Provider | Supported Service | Where to Get a Key |
|---|---|---|
| `gemini` | Google Gemini (Fast & inexpensive) | [Google AI Studio](https://aistudio.google.com/apikey) |
| `openai` | OpenAI (GPT-4o, GPT-4o-mini) | [OpenAI Platform](https://platform.openai.com/api-keys) |
| `xai` | Grok (xAI) | [xAI Console](https://console.x.ai) |
| `groq` | Groq (Llama 3.3, ultra-low latency) | [Groq Console](https://console.groq.com/keys) |
| `openrouter` | OpenRouter (Aggregated providers) | [OpenRouter Keys](https://openrouter.ai/keys) |
| `anthropic` | Anthropic Claude | [Anthropic Console](https://console.anthropic.com) |
| `ollama` | Local Ollama instance (No key required) | [Ollama](https://ollama.com) |
| `custom` | Any OpenAI-compatible endpoint | Provide `CLIPSORA_AI_BASE_URL` |

*Note: Speech-to-text runs entirely on your own processor by default. Audio never leaves your system.*

---

## Caption Styles & Layout Frames

Every clip look combines a **caption preset** with a **frame layout**:

- **14 Caption Styles:**
  - *Clean:* Clean, Minimal, Podcast, Classic
  - *Popular / Bold:* Bounce, Hype, Kinetic Highlight
  - *Cinematic:* Cinematic, Editorial
  - *Social & Playful:* Gamer, Stacked, Karaoke, Typewriter, Glitch
- **16 Video Frames:**
  - Blurred background fill, full zoom, center crop, letterbox, side-by-side, picture-in-picture, facecam gaming layout, quote canvas, and branded borders.
- **Customization Panel:**
  - Fine-tune font sizes, outline thickness, colors, text shadows, casing, line breaks, positioning, and animation effects. Changes can be applied per-clip without affecting others.

See [docs/CAPTION_LAYOUT_SYSTEM.md](docs/CAPTION_LAYOUT_SYSTEM.md) for layout formulas and rendering details.

---

## Production & Multi-User Deployment

For team setups or shared servers:
- **Turn on authentication:** Set `CLIPSORA_ACCOUNTS=1` in `.env` to require login and separate accounts.
- **Docker Compose:** Use the provided [`docker-compose.yml`](docker-compose.yml) with automatic PostgreSQL database management and HTTPS via Caddy:
  ```bash
  cp .env.example .env
  # Set CLIPSORA_DOMAIN, POSTGRES_PASSWORD, and COMPOSE_PROFILES=own-https
  docker compose up -d --build
  ```
- **Admin tools:** Grant admin privileges from the terminal:
  ```bash
  docker compose exec app python -m studio.admin grant user@example.com
  ```

Detailed production setup guides, reverse proxy configurations (Nginx/Traefik), and social media OAuth instructions can be found in [DEPLOY.md](DEPLOY.md).

---

## Project Structure

| Directory / File | Description |
|---|---|
| `studio/` | Backend engine: FastAPI server, pipeline orchestrator, live stream buffer, render queue |
| `studio/styles.py` | Definitions for the 14 caption presets and 16 frame layouts |
| `studio/render.py` | Video rendering, ffmpeg filter graph generator, Pillow text drawing |
| `studio/ai.py` | Unified AI provider client (Gemini, OpenAI, Anthropic, Groq, Ollama) |
| `studio/transcribe.py` | On-device speech recognition via `sherpa-onnx` and Parakeet model |
| `studio/fonts/` | Bundled open-source typography used for clip rendering |
| `web/` | Web dashboard: pure HTML, CSS tokens, and JavaScript (zero build step) |
| `tests/` | Automated test suite verifying auth, processing queues, and security |

---

## Testing

Run the automated test suite against an isolated, throwaway instance:

```bash
python tests/run.py
```

Tests run on an ephemeral port with a temporary data directory and do not touch your actual database or API keys.

---

## Credits & Acknowledgements

Clipsora is built on top of excellent open-source software, models, and typography:

### Fonts & Typography

The clip rendering engine ships with the following open-source fonts, distributed under the [SIL Open Font License (OFL) 1.1](http://scripts.sil.org/OFL):

- **[Anton](https://github.com/googlefonts/AntonFont.git)**
  - Copyright &copy; 2020 The Anton Project Authors
  - Designed by Vernon Adams
  - License: SIL Open Font License 1.1 ([studio/fonts/OFL-anton.txt](studio/fonts/OFL-anton.txt))
- **[Archivo Black](https://github.com/Omnibus-Type/ArchivoBlack)**
  - Copyright &copy; 2017 The Archivo Black Project Authors
  - Designed by Omnibus-Type (Héctor Gatti)
  - License: SIL Open Font License 1.1 ([studio/fonts/OFL-archivoblack.txt](studio/fonts/OFL-archivoblack.txt))
- **[Poppins](https://github.com/itfoundry/Poppins)**
  - Copyright &copy; 2020 The Poppins Project Authors
  - Designed by Indian Type Foundry (Ninad Kale, Jonny Pinhorn)
  - License: SIL Open Font License 1.1 ([studio/fonts/OFL-poppins.txt](studio/fonts/OFL-poppins.txt))
- **[Geist](https://vercel.com/font)**
  - Copyright &copy; Vercel, Inc.
  - Used in the web interface via Google Fonts under SIL Open Font License 1.1

### Core Libraries & Tools

- **[FFmpeg](https://ffmpeg.org/)** &mdash; Multimedia encoding, filtering, and video assembly.
- **[sherpa-onnx](https://github.com/k2-fsa/sherpa-onnx)** &mdash; Fast, private offline speech-to-text using the NeMo Parakeet TDT model.
- **[yt-dlp](https://github.com/yt-dlp/yt-dlp)** &mdash; Media extraction and stream recording.
- **[FastAPI](https://fastapi.tiangolo.com/) & [Uvicorn](https://www.uvicorn.org/)** &mdash; Asynchronous web server and API backbone.
- **[Pillow](https://python-pillow.org/)** &mdash; Image synthesis and font rasterization.
- **[Deno](https://deno.com/)** &mdash; Sandboxed JavaScript runtime used for modern media extractors.

---

## License & Credits

- Clipsora is licensed under the [MIT License](LICENSE).
- Bundled fonts located in `studio/fonts/` are licensed under the [SIL Open Font License 1.1](http://scripts.sil.org/OFL) with license texts included in their respective files.
- For complete third-party licenses, font attributions, and copyright disclosures, see **[CREDITS.md](CREDITS.md)**.
