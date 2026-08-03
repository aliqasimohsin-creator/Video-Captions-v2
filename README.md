# Video Captioning - v2

A drag-and-drop tool that takes a video, transcribes the speech (any language,
auto-detected), romanizes non-Latin script (e.g. Hindi/Urdu -> Hinglish/Roman
Urdu), lets you edit and style the captions in a full visual timeline, and
renders the video back out with styled, animated captions burned in using
Remotion — preserving the original video's resolution, frame rate, and
bitrate.

Pipeline: **Gradio UI -> AssemblyAI (transcription) -> Gemini (romanization)
-> Remotion (rendering)**.

## What's new in v2

- **Visual timeline editor** — a professional-editor-style timeline with
  separate video (thumbnail filmstrip), audio (waveform), and captions
  tracks, all on a shared, zoomable time axis. Drag a caption to move it,
  drag its edges to resize it, click its text to open a full editor popup,
  or drag on empty track space to create a new caption.
- **Live style preview** — font, size, text/outline color, background style,
  and entrance animation (pop/fade/slide, with a pop-intensity slider) all
  update instantly in both a compact preview panel and directly on the
  timeline's video, matching what the final render will look like.
- **Persistence** — style preferences and your in-progress editing session
  survive a page refresh (saved to the browser's `localStorage`).
- **Real render progress** — a live progress bar tracks actual render
  completion (frame-by-frame), not just a spinner.
- **Original quality preserved** — the rendered output keeps the source
  video's frame rate and bitrate, and its resolution (cropped to your chosen
  orientation using the largest region that fits the source, so a
  high-resolution source doesn't get downscaled to a fixed preset).
- **Start Over** — reset the whole session and pick a new video without
  restarting the app.

## Prerequisites

- **Python 3.12** (or close to it) — https://www.python.org/downloads/
- **Node.js 18+** and **npm** — https://nodejs.org/
- An **AssemblyAI** API key (free tier available) — https://www.assemblyai.com/
- A **Google Gemini** API key (free tier, no billing needed) — https://aistudio.google.com/

## 1. Get the code and install Python dependencies

From the project root:

```bash
# (optional but recommended) create a virtual environment
python -m venv .venv

# activate it
.venv\Scripts\activate        # Windows
source .venv/bin/activate     # macOS/Linux

# install Python dependencies
pip install -r requirements.txt
```

## 2. Install the Remotion (Node.js) renderer

```bash
cd renderer
npm install
cd ..
```

## 3. Add your API keys

Open both **`transcribe.py`** and **`run_pipeline.py`** and replace the
placeholders with your own keys:

```python
# AssemblyAI key — used for transcription (in both files)
aai.settings.api_key = "ENTER_YOUR_ASSEMBLY_AI_API_HERE"

# Gemini key — used for romanization (run_pipeline.py only)
gemini_client = genai.Client(api_key="ENTER_YOUR_GEMINI_AI_API_HERE")
```

- AssemblyAI key: sign up and grab it from your dashboard at
  https://www.assemblyai.com/
- Gemini key: sign up and grab it from https://aistudio.google.com/
  (the free tier is enough, no billing setup required)

Never commit real API keys back into this repo — keep them local.

## 4. Run the app

```bash
python app.py
```

This launches a local Gradio web UI (the terminal will print a URL like
`http://127.0.0.1:7860`). Open it in your browser:

1. Upload a video and click **1. Transcribe**.
2. Edit captions and drag/resize them on the timeline, tweak the caption
   style (font, colors, animation, position) using the live preview to
   guide you.
3. Click **2. Render Video**. You can tweak the style and click render
   again as many times as you like without re-transcribing.

## How it works under the hood

1. **`app.py`** — the Gradio UI: upload/transcribe/render controls, style
   controls with a live preview, and the timeline editor's HTML/state wiring
   (including `localStorage`-based persistence).
2. **`static/timeline/`** — the timeline editor's client-side code
   (`timeline.js`/`timeline.css`), built on a vendored `wavesurfer.js` for
   the waveform track, plus custom drag/resize logic for the captions track
   and thumbnail extraction for the video track.
3. **`run_pipeline.py`** — the pipeline: copies your video locally, sends it
   to AssemblyAI for transcription, uses Gemini to romanize any non-Latin
   script words, groups words into caption chunks, probes the source
   video's resolution/fps/bitrate with `ffprobe`, writes everything to
   `renderer/captions.json`, then calls Remotion to render the final video
   (reporting live per-frame progress back to the UI).
4. **`group_into_captions.py`** — groups word-level timestamps into small
   multi-word caption chunks.
5. **`renderer/`** — a Remotion project that reads `captions.json` and
   burns the styled, animated captions into the video at the source's
   original resolution/fps/bitrate (`npx remotion render`).

Rendered output ends up in `renderer/out/`.

## Troubleshooting

- **`npx remotion render` fails** — make sure you ran `npm install` inside
  `renderer/` (step 2).
- **Transcription errors** — double check your AssemblyAI key is correct and
  has remaining quota.
- **Romanization step fails / mismatched word count** — this only affects
  non-Latin script text; the pipeline automatically falls back to the
  original transcript text if Gemini's response doesn't line up.
- **`ffprobe` not found** — the pipeline first looks for a system-installed
  `ffprobe` on your `PATH`; if missing, it falls back to the copy already
  bundled with Remotion's renderer in `renderer/node_modules/@remotion/`
  (Windows, macOS Intel/Apple Silicon, and Linux x64/arm64 are all covered
  automatically by `npm install`, so this should just work without
  installing `ffmpeg` yourself on any platform).
