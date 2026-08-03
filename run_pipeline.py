import re
import subprocess
import sys
import json
import shutil
import time
from fractions import Fraction
from pathlib import Path

import assemblyai as aai
from google import genai
from group_into_captions import group_words_into_chunks

aai.settings.api_key = "ENTER_YOUR_ASSEMBLY_AI_API_HERE"
gemini_client = genai.Client(api_key="ENTER_YOUR_GEMINI_AI_API_HERE")

RENDERER_DIR = Path("renderer")
PUBLIC_DIR = RENDERER_DIR / "public"
WORK_DIR = Path("work")

FFPROBE_PATH = shutil.which("ffprobe") or str(
    RENDERER_DIR / "node_modules" / "@remotion" / "compositor-win32-x64-msvc" / "ffprobe.exe"
)


def make_local_working_copy(video_path: str) -> str:
    WORK_DIR.mkdir(parents=True, exist_ok=True)
    local_path = WORK_DIR / Path(video_path).name

    max_attempts = 5
    delay_seconds = 0.5
    last_error = None

    for attempt in range(1, max_attempts + 1):
        try:
            shutil.copy(video_path, local_path)
            return str(local_path)
        except PermissionError as e:
            last_error = e
            if attempt < max_attempts:
                time.sleep(delay_seconds)

    raise RuntimeError(
        f"Could not read the uploaded video after {max_attempts} attempts "
        f"(file may be locked by another process): {last_error}"
    )


def romanize_words(words: list) -> list:
    original_texts = [w["text"] for w in words]

    prompt = f"""Here is a JSON array of words from a speech transcript, in order.
Some words are already in English/Latin script. Others are in Devanagari
or Urdu (Arabic) script.

Return a JSON array of the SAME LENGTH, in the SAME ORDER, where:
- Any word already in Latin script is returned unchanged
- Any Hindi/Urdu word is transliterated into casual Roman script, the way
  people naturally type it informally (e.g. "ja raha hun tou kya"), NOT
  formal academic transliteration with diacritics

Return ONLY the JSON array and nothing else — no explanation, no markdown.

Input: {json.dumps(original_texts, ensure_ascii=False)}"""

    try:
        response = gemini_client.models.generate_content(
            model="gemini-3.6-flash",
            contents=prompt,
        )

        raw_text = response.text.strip()
        raw_text = raw_text.removeprefix("```json").removeprefix("```").removesuffix("```").strip()

        romanized_texts = json.loads(raw_text)
    except Exception as e:
        print(f"Warning: romanization request failed ({e}) — keeping original script.")
        return words

    if len(romanized_texts) != len(words):
        print("Warning: romanization word count mismatch — keeping original script.")
        return words

    for word, new_text in zip(words, romanized_texts):
        word["text"] = new_text

    return words


def start_transcription(video_path: str) -> tuple[str, list]:
    local_video_path = make_local_working_copy(video_path)
    return local_video_path, transcribe_and_chunk(local_video_path)


def rebuild_word_timings(text: str, start: float, end: float) -> list[dict]:
    tokens = text.split()
    if not tokens:
        return []
    step = max(end - start, 0.0) / len(tokens)
    return [
        {"text": t, "start": start + i * step, "end": start + (i + 1) * step}
        for i, t in enumerate(tokens)
    ]


def finish_captioned_render(
    local_video_path: str,
    captions: list,
    orientation: str,
    caption_position: str,
    caption_style: dict,
    output_filename: str = None,
    progress_callback=None,
) -> str:
    # A unique filename per render (instead of always overwriting output.mp4) means the
    # browser can never mistake a stale cached video for a fresh one after re-rendering.
    if output_filename is None:
        output_filename = f"output_{int(time.time())}.mp4"
    cleaned = []
    for chunk in captions:
        text = (chunk.get("text") or "").strip()
        start, end = chunk.get("start", 0), chunk.get("end", 0)
        if not text or end <= start:
            continue
        cleaned.append({
            "text": text,
            "start": start,
            "end": end,
            "words": rebuild_word_timings(text, start, end),
        })
    cleaned.sort(key=lambda c: c["start"])

    if not cleaned:
        raise ValueError("No caption chunks to render.")

    props_path, bitrate = prepare_remotion_inputs(local_video_path, cleaned, orientation, caption_position, caption_style)
    output_path = render_video(props_path, output_filename, bitrate=bitrate, progress_callback=progress_callback)
    # Deliberately NOT deleting local_video_path here — the whole point of "change a
    # style setting and click Render again" is that the same working copy is reused
    # for every render of this session. It only gets cleaned up when a new
    # transcription starts (run_transcription) or the user clicks Start Over.
    return str(output_path)


def transcribe_and_chunk(video_path: str):
    transcriber = aai.Transcriber()
    config = aai.TranscriptionConfig(language_detection=True)
    transcript = transcriber.transcribe(video_path, config=config)

    word_data = [
        {"text": w.text, "start": w.start / 1000, "end": w.end / 1000}
        for w in (transcript.words or [])
    ]

    word_data = romanize_words(word_data)

    return group_words_into_chunks(word_data, chunk_size=2)


def probe_video_metadata(video_path: str) -> dict:
    result = subprocess.run(
        [
            FFPROBE_PATH, "-v", "error", "-select_streams", "v:0",
            "-show_entries", "stream=width,height,r_frame_rate,bit_rate",
            "-show_entries", "format=bit_rate",
            "-of", "json", video_path,
        ],
        capture_output=True, text=True, check=True,
    )
    data = json.loads(result.stdout)
    stream = data["streams"][0]
    fps = float(Fraction(stream["r_frame_rate"]))
    bitrate = stream.get("bit_rate") or data.get("format", {}).get("bit_rate")
    return {
        "width": stream["width"],
        "height": stream["height"],
        "fps": fps,
        "bitrate": int(bitrate) if bitrate else None,
    }


def prepare_remotion_inputs(video_path: str, captions: list, orientation: str, caption_position: str, caption_style: dict):
    video_filename = Path(video_path).name
    PUBLIC_DIR.mkdir(parents=True, exist_ok=True)
    shutil.copy(video_path, PUBLIC_DIR / video_filename)

    metadata = probe_video_metadata(video_path)

    props = {
        "videoFile": video_filename,
        "captions": captions,
        "orientation": orientation,
        "captionPosition": caption_position,
        "captionStyle": caption_style,
        "sourceWidth": metadata["width"],
        "sourceHeight": metadata["height"],
        "fps": metadata["fps"],
    }

    props_path = RENDERER_DIR / "captions.json"
    with open(props_path, "w") as f:
        json.dump(props, f, indent=2)

    return props_path, metadata["bitrate"]


RENDER_PROGRESS_PATTERN = re.compile(r"Rendered (\d+)/(\d+)")


def render_video(props_path: Path, output_filename: str = "output.mp4", bitrate: int = None, progress_callback=None):
    """progress_callback(done, total), if given, is called (from this same thread,
    between polls) as "Rendered X/Y" lines show up in the render's output, so a
    caller (e.g. Gradio) can show real render progress instead of just a spinner.

    Output is redirected to a log file and polled periodically rather than reading
    the subprocess's stdout pipe directly — blocking line-by-line pipe reads from a
    background thread turned out to hang indefinitely under Gradio's worker-thread +
    asyncio event loop on Windows, even though the exact same subprocess call works
    fine standalone. Polling a file sidesteps that pipe/event-loop interaction.
    """
    output_path = f"out/{output_filename}"
    log_path = RENDERER_DIR / "out" / f"{Path(output_filename).stem}.render.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)

    render_args = [
        "npx", "remotion", "render",
        "CaptionedVideo",
        output_path,
        f"--props={props_path.name}",
    ]
    if bitrate:
        render_args.append(f"--video-bitrate={round(bitrate / 1000)}K")

    # shell=True with a list of args only works correctly on Windows (where it joins
    # the list into a single command line and runs it via cmd.exe, which is also what
    # resolves the "npx" -> "npx.cmd" shim). On POSIX, shell=True with a list instead
    # treats args[0] as the entire shell command and the rest as arguments to the
    # shell itself, silently dropping them — so npx would run with no arguments at
    # all. A real executable like npx on POSIX doesn't need shell interpretation.
    use_shell = sys.platform == "win32"

    with open(log_path, "w") as log_file:
        process = subprocess.Popen(
            render_args,
            cwd=RENDERER_DIR,
            shell=use_shell,
            stdout=log_file,
            stderr=subprocess.STDOUT,
        )

        last_pos = 0
        while process.poll() is None:
            time.sleep(0.4)
            with open(log_path) as f:
                f.seek(last_pos)
                new_text = f.read()
                last_pos = f.tell()
            for line in new_text.splitlines():
                print(line)
                match = RENDER_PROGRESS_PATTERN.search(line)
                if match and progress_callback:
                    progress_callback(int(match.group(1)), int(match.group(2)))

    with open(log_path) as f:
        full_output = f.read()
    log_path.unlink(missing_ok=True)

    if process.returncode != 0:
        raise RuntimeError("Remotion render failed:\n" + "\n".join(full_output.splitlines()[-20:]))

    return RENDERER_DIR / output_path


DEFAULT_CAPTION_STYLE = {
    "fontFamily": "Montserrat",
    "fontSize": 76,
    "textColor": "#ffffff",
    "strokeColor": "#000000",
    "strokeEnabled": True,
    "background": "none",
    "animation": "pop",
}


def generate_captioned_video(
    video_path: str,
    orientation: str = "horizontal",
    caption_position: str = "bottom",
    caption_style: dict = None,
) -> str:
    if caption_style is None:
        caption_style = DEFAULT_CAPTION_STYLE

    local_video_path = make_local_working_copy(video_path)

    try:
        captions = transcribe_and_chunk(local_video_path)
        props_path, bitrate = prepare_remotion_inputs(local_video_path, captions, orientation, caption_position, caption_style)
        output_path = render_video(props_path, bitrate=bitrate)
        return str(output_path)
    finally:
        Path(local_video_path).unlink(missing_ok=True)


if __name__ == "__main__":
    result_path = generate_captioned_video("path/to/your/video.mp4")
    print(f"Done! Video saved to {result_path}")
