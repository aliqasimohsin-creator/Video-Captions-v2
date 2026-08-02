import subprocess
import json
import shutil
import time
from pathlib import Path

import assemblyai as aai
from google import genai
from group_into_captions import group_words_into_chunks

aai.settings.api_key = "Enter Your Assembly AI API here"
gemini_client = genai.Client(api_key="Enter Your Gemini API here")

RENDERER_DIR = Path("renderer")
PUBLIC_DIR = RENDERER_DIR / "public"
WORK_DIR = Path("work")


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

    response = gemini_client.models.generate_content(
        model="gemini-3.6-flash",
        contents=prompt,
    )

    raw_text = response.text.strip()
    raw_text = raw_text.removeprefix("```json").removeprefix("```").removesuffix("```").strip()

    romanized_texts = json.loads(raw_text)

    if len(romanized_texts) != len(words):
        print("Warning: romanization word count mismatch — keeping original script.")
        return words

    for word, new_text in zip(words, romanized_texts):
        word["text"] = new_text

    return words


def transcribe_and_chunk(video_path: str):
    transcriber = aai.Transcriber()
    config = aai.TranscriptionConfig(language_detection=True)
    transcript = transcriber.transcribe(video_path, config=config)

    word_data = [
        {"text": w.text, "start": w.start / 1000, "end": w.end / 1000}
        for w in transcript.words
    ]

    word_data = romanize_words(word_data)

    return group_words_into_chunks(word_data, chunk_size=2)


def prepare_remotion_inputs(video_path: str, captions: list, orientation: str, caption_position: str, caption_style: dict):
    video_filename = Path(video_path).name
    PUBLIC_DIR.mkdir(parents=True, exist_ok=True)
    shutil.copy(video_path, PUBLIC_DIR / video_filename)

    props = {
        "videoFile": video_filename,
        "captions": captions,
        "orientation": orientation,
        "captionPosition": caption_position,
        "captionStyle": caption_style,
    }

    props_path = RENDERER_DIR / "captions.json"
    with open(props_path, "w") as f:
        json.dump(props, f, indent=2)

    return props_path


def render_video(props_path: Path, output_filename: str = "output.mp4"):
    output_path = f"out/{output_filename}"

    result = subprocess.run(
        [
            "npx", "remotion", "render",
            "CaptionedVideo",
            output_path,
            f"--props={props_path.name}",
        ],
        cwd=RENDERER_DIR,
        shell=True,
    )

    if result.returncode != 0:
        raise RuntimeError("Remotion render failed — check the terminal output above for details.")

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
        props_path = prepare_remotion_inputs(local_video_path, captions, orientation, caption_position, caption_style)
        output_path = render_video(props_path)
        return str(output_path)
    finally:
        Path(local_video_path).unlink(missing_ok=True)


if __name__ == "__main__":
    result_path = generate_captioned_video("path/to/your/video.mp4")
    print(f"Done! Video saved to {result_path}")
