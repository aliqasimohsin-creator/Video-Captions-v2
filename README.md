# Video Captioning Tool

A drag-and-drop tool that takes a video, transcribes the speech (any language,
auto-detected), romanizes non-Latin script (e.g. Hindi/Urdu -> Hinglish/Roman
Urdu), groups words into short caption chunks, and renders the video back out
with styled, animated captions burned in using Remotion.

Pipeline: **Gradio UI -> AssemblyAI (transcription) -> Gemini (romanization)
-> Remotion (rendering)**.

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
`"Enter Your API here"` placeholders with your own keys:

```python
# AssemblyAI key — used for transcription (in both files)
aai.settings.api_key = "Enter Your API here"

# Gemini key — used for romanization (run_pipeline.py only)
gemini_client = genai.Client(api_key="Enter Your API here")
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
`http://127.0.0.1:7860`). Open it in your browser, upload a video, choose
your caption style, and click **Generate Captions**.

## How it works under the hood

1. **`app.py`** — the Gradio UI (upload video, style controls, live preview).
2. **`run_pipeline.py`** — the pipeline: copies your video locally, sends it
   to AssemblyAI for transcription, uses Gemini to romanize any non-Latin
   script words, groups words into caption chunks, writes them to
   `renderer/captions.json`, then calls Remotion to render the final video.
3. **`group_into_captions.py`** — groups word-level timestamps into small
   multi-word caption chunks.
4. **`renderer/`** — a Remotion project that reads `captions.json` and
   burns the styled captions into the video (`npx remotion render`).

Rendered output ends up in `renderer/out/`.

## Troubleshooting

- **`npx remotion render` fails** — make sure you ran `npm install` inside
  `renderer/` (step 2).
- **Transcription errors** — double check your AssemblyAI key is correct and
  has remaining quota.
- **Romanization step fails / mismatched word count** — this only affects
  non-Latin script text; the pipeline automatically falls back to the
  original transcript text if Gemini's response doesn't line up.
