from pathlib import Path

import gradio as gr
from run_pipeline import start_transcription, finish_captioned_render

gr.set_static_paths(paths=[str(Path("static").resolve()), str(Path("work").resolve())])

BACKGROUND_MAP = {
    "None (outline only)": "none",
    "Solid box": "box",
    "Highlight current word": "highlight-word",
}

ANIMATION_MAP = {
    "Pop / scale": "pop",
    "Simple fade": "fade",
    "Slide up": "slide",
}

POSITION_MAP = {"Top": "top", "Center": "center", "Bottom-third": "bottom"}

DEFAULTS = dict(
    orientation="Horizontal (1920x1080)",
    position="Bottom-third",
    font="Montserrat",
    font_size=76,
    text_color="#FFFFFF",
    stroke_color="#000000",
    stroke_enabled=True,
    background="None (outline only)",
    animation="Pop / scale",
    pop_intensity=65,
)

CUSTOM_CSS = """
#header { text-align: center; margin-bottom: 0.5rem; }
#preview-box { display: flex; justify-content: center; padding: 0.5rem 0; }
#status-text { min-height: 1.5em; }
"""

# The static file route serves timeline.js/css with no Cache-Control header at all,
# so browsers are free to keep serving a stale cached copy indefinitely across code
# changes. Busting the URL with the file's own mtime guarantees a fresh fetch whenever
# the file actually changes, without needing a hard-refresh.
def _static_version(relative_path: str) -> int:
    path = Path("static") / relative_path
    return int(path.stat().st_mtime) if path.exists() else 0


TIMELINE_LOAD_JS = """
() => {
    const link = document.createElement("link");
    link.rel = "stylesheet";
    link.href = "/gradio_api/file=static/timeline/timeline.css?v=__CSS_VERSION__";
    document.head.appendChild(link);

    const script = document.createElement("script");
    script.type = "module";
    script.src = "/gradio_api/file=static/timeline/timeline.js?v=__JS_VERSION__";
    document.head.appendChild(script);

    // Loaded once here instead of inside build_preview_html's returned HTML —
    // re-injecting a @import stylesheet on every style tweak caused noticeable
    // lag while dragging color pickers.
    const fontLink = document.createElement("link");
    fontLink.rel = "stylesheet";
    fontLink.href = "https://fonts.googleapis.com/css2?family=Montserrat:wght@700&family=Poppins:wght@700&family=Inter:wght@700&family=Bebas+Neue&display=swap";
    document.head.appendChild(fontLink);
}
""".replace("__CSS_VERSION__", str(_static_version("timeline/timeline.css"))).replace(
    "__JS_VERSION__", str(_static_version("timeline/timeline.js"))
)

STYLE_SYNC_JS = """
(orientationLabel, positionLabel, font, fontSize, textColor, strokeColor, strokeEnabled, backgroundLabel) => {
    const POSITION_MAP = {"Top": "top", "Center": "center", "Bottom-third": "bottom"};
    const BACKGROUND_MAP = {"None (outline only)": "none", "Solid box": "box", "Highlight current word": "highlight-word"};
    const frameWidth = orientationLabel.startsWith("Vertical") ? 1080 : 1920;
    if (window.__updateCaptionStyle) {
        window.__updateCaptionStyle({
            fontFamily: font,
            fontSize: fontSize,
            textColor: textColor,
            strokeColor: strokeColor,
            strokeEnabled: strokeEnabled,
            background: BACKGROUND_MAP[backgroundLabel],
            position: POSITION_MAP[positionLabel],
            frameWidth: frameWidth,
        });
    }
    const existing = JSON.parse(localStorage.getItem("caption_style_prefs") || "{}");
    localStorage.setItem("caption_style_prefs", JSON.stringify({
        ...existing,
        orientationLabel, positionLabel, font, fontSize, textColor, strokeColor, strokeEnabled, backgroundLabel,
    }));
    return [];
}
"""

ANIMATION_SYNC_JS = """
(animationLabel, popIntensity) => {
    const ANIMATION_MAP = {"Pop / scale": "pop", "Simple fade": "fade", "Slide up": "slide"};
    if (window.__updateCaptionStyle) {
        window.__updateCaptionStyle({
            animation: ANIMATION_MAP[animationLabel],
            popIntensity: popIntensity,
        });
    }
    const existing = JSON.parse(localStorage.getItem("caption_style_prefs") || "{}");
    localStorage.setItem("caption_style_prefs", JSON.stringify({
        ...existing,
        animationLabel, popIntensity,
    }));
    return [];
}
"""

RESTORE_PREFS_JS = """
() => {
    const raw = localStorage.getItem("caption_style_prefs");
    return [raw ? JSON.parse(raw) : null];
}
"""

RESTORE_SESSION_JS = """
() => {
    const raw = localStorage.getItem("caption_session");
    return [raw ? JSON.parse(raw) : null];
}
"""

SAVE_SESSION_JS = """
(captions) => {
    function tryInit(attemptsLeft) {
        if (window.__initCaptionTimeline) {
            window.__initCaptionTimeline(captions);
        } else if (attemptsLeft > 0) {
            setTimeout(() => tryInit(attemptsLeft - 1), 150);
        }
    }
    tryInit(40);

    function trySave(attemptsLeft) {
        const videoEl = document.getElementById("timeline-video");
        if (!videoEl || !videoEl.src) {
            if (attemptsLeft > 0) setTimeout(() => trySave(attemptsLeft - 1), 150);
            return;
        }
        const marker = "/gradio_api/file=";
        const idx = videoEl.src.indexOf(marker);
        const localVideoPath = idx >= 0 ? decodeURIComponent(videoEl.src.slice(idx + marker.length)) : null;
        if (localVideoPath) {
            localStorage.setItem("caption_session", JSON.stringify({ localVideoPath, captions, videoSrc: videoEl.src }));
        }
    }
    trySave(40);
}
"""


def build_preview_html(
    orientation_label,
    position_label,
    font,
    font_size,
    text_color,
    stroke_color,
    stroke_enabled,
    background_label,
):
    orientation = "vertical" if orientation_label.startswith("Vertical") else "horizontal"
    position = POSITION_MAP[position_label]
    background = BACKGROUND_MAP[background_label]

    preview_width = 300
    frame_w, frame_h = (1080, 1920) if orientation == "vertical" else (1920, 1080)
    preview_height = round(preview_width * frame_h / frame_w)
    scaled_font_size = max(10, round(font_size * (preview_width / frame_w)))

    stroke_css = ""
    if stroke_enabled:
        stroke_css = (
            f"text-shadow: -1px -1px 0 {stroke_color}, 1px -1px 0 {stroke_color}, "
            f"-1px 1px 0 {stroke_color}, 1px 1px 0 {stroke_color};"
        )

    bg_css = ""
    sample_text = "This is sample text"
    if background == "box":
        bg_css = "background: rgba(0,0,0,0.65); padding: 6px 14px; border-radius: 6px;"
    elif background == "highlight-word":
        sample_text = (
            f'This is <span style="background:{text_color}; color:#000; '
            'padding:0 4px; border-radius:3px;">sample</span> text'
        )

    position_css = {
        "top": "align-items: flex-start; padding-top: 10%;",
        "center": "align-items: center;",
        "bottom": "align-items: flex-end; padding-bottom: 10%;",
    }[position]

    return f"""
    <div style="width:{preview_width}px;height:{preview_height}px;background:#111;
                display:flex;justify-content:center;{position_css}
                border-radius:10px;overflow:hidden;border:1px solid #333;">
      <div style="font-family:'{font}',sans-serif;font-size:{scaled_font_size}px;font-weight:700;
                  color:{text_color};{stroke_css}{bg_css}text-align:center;max-width:90%;line-height:1.2;">
        {sample_text}
      </div>
    </div>
    """


def build_timeline_html(video_src: str) -> str:
    return f"""
    <div id="timeline-editor">
      <div class="timeline-video-wrap">
        <video id="timeline-video" src="{video_src}" controls></video>
        <div id="timeline-caption-overlay"></div>
      </div>
      <div class="timeline-toolbar">
        <p id="timeline-hint">Drag a caption to move it, drag its edges to resize it, click its text to open
        the full editor, and drag on empty captions-track space to add a new one. Use × to delete.</p>
        <div class="timeline-zoom">
          <button id="timeline-zoom-out" type="button" title="Zoom out">−</button>
          <button id="timeline-zoom-in" type="button" title="Zoom in">+</button>
        </div>
      </div>
      <div id="timeline-tracks">
        <div class="timeline-track-row">
          <div class="timeline-track-label">Video</div>
          <div id="filmstrip-track" class="timeline-track-content timeline-track-filmstrip"></div>
        </div>
        <div class="timeline-track-row">
          <div class="timeline-track-label">Audio</div>
          <div id="waveform-track" class="timeline-track-content timeline-track-waveform"></div>
        </div>
        <div class="timeline-track-row">
          <div class="timeline-track-label">Captions</div>
          <div id="captions-track" class="timeline-track-content timeline-track-captions"></div>
        </div>
      </div>
    </div>
    """


def run_transcription(video_path, previous_local_path):
    if not video_path:
        return gr.update(), gr.update(), gr.update(), gr.update(), "⚠️ Please upload a video first.", gr.update()

    if previous_local_path:
        try:
            Path(previous_local_path).unlink(missing_ok=True)
        except PermissionError:
            pass  # still open (e.g. the browser's video element) — clean up next time

    try:
        local_video_path, captions = start_transcription(video_path)
    except Exception as e:
        return gr.update(), gr.update(), gr.update(), gr.update(), f"❌ Transcription failed: {e}", gr.update()

    video_src = f"/gradio_api/file={Path(local_video_path).resolve().as_posix()}"
    timeline_html_value = build_timeline_html(video_src)

    return (
        local_video_path,
        captions,
        gr.update(visible=True),
        timeline_html_value,
        "✅ Transcribed! Edit the captions below, then render.",
        gr.update(interactive=True),
    )


def run_render(
    local_video_path,
    captions,
    orientation_label,
    position_label,
    font,
    font_size,
    text_color,
    stroke_color,
    stroke_enabled,
    background_label,
    animation_label,
    pop_intensity_value,
    progress=gr.Progress(),
):
    if not local_video_path or not captions:
        return gr.update(), "⚠️ Please transcribe a video first."

    orientation = "vertical" if orientation_label.startswith("Vertical") else "horizontal"

    caption_style = {
        "fontFamily": font,
        "fontSize": font_size,
        "textColor": text_color,
        "strokeColor": stroke_color,
        "strokeEnabled": stroke_enabled,
        "background": BACKGROUND_MAP[background_label],
        "animation": ANIMATION_MAP[animation_label],
        "popIntensity": pop_intensity_value,
    }

    def report_progress(done, total):
        progress(done / max(total, 1), desc=f"Rendering frame {done}/{total}")

    try:
        output_path = finish_captioned_render(
            local_video_path,
            captions,
            orientation,
            POSITION_MAP[position_label],
            caption_style,
            progress_callback=report_progress,
        )
    except Exception as e:
        return gr.update(), f"❌ Something went wrong: {e}"

    return output_path, "✅ Done! Your captioned video is ready below."


def show_transcribing_status():
    return gr.update(interactive=False), "⏳ Transcribing... this can take a minute or two."


def show_rendering_status():
    return gr.update(interactive=False), "⏳ Rendering... this can take a few minutes depending on video length."


def reset_style():
    return (
        DEFAULTS["font"],
        DEFAULTS["font_size"],
        DEFAULTS["text_color"],
        DEFAULTS["stroke_color"],
        DEFAULTS["stroke_enabled"],
        DEFAULTS["background"],
        DEFAULTS["animation"],
        DEFAULTS["pop_intensity"],
    )


def start_over(local_video_path):
    if local_video_path:
        try:
            Path(local_video_path).unlink(missing_ok=True)
        except PermissionError:
            pass  # still open (e.g. the browser's video element) — harmless to leave behind
    return (
        None,  # local_video_state
        None,  # hidden_captions
        gr.update(visible=False),  # timeline_group
        "",  # timeline_html
        gr.update(value=None),  # video_input
        gr.update(interactive=False),  # transcribe_btn
        gr.update(interactive=False),  # render_btn
        None,  # output_video
        "",  # status_text
    )


def restore_preferences(prefs):
    if not prefs:
        return [gr.update()] * 10
    return [
        gr.update(value=prefs.get("orientationLabel", DEFAULTS["orientation"])),
        gr.update(value=prefs.get("positionLabel", DEFAULTS["position"])),
        gr.update(value=prefs.get("font", DEFAULTS["font"])),
        gr.update(value=prefs.get("fontSize", DEFAULTS["font_size"])),
        gr.update(value=prefs.get("textColor", DEFAULTS["text_color"])),
        gr.update(value=prefs.get("strokeColor", DEFAULTS["stroke_color"])),
        gr.update(value=prefs.get("strokeEnabled", DEFAULTS["stroke_enabled"])),
        gr.update(value=prefs.get("backgroundLabel", DEFAULTS["background"])),
        gr.update(value=prefs.get("animationLabel", DEFAULTS["animation"])),
        gr.update(value=prefs.get("popIntensity", DEFAULTS["pop_intensity"])),
    ]


def restore_session(stored):
    no_op = (gr.update(), gr.update(), gr.update(), gr.update(), gr.update(), gr.update())
    if not stored or not stored.get("localVideoPath"):
        return no_op

    local_video_path = stored["localVideoPath"]
    if not Path(local_video_path).exists():
        return no_op

    captions = stored.get("captions") or []
    video_src = stored.get("videoSrc") or f"/gradio_api/file={Path(local_video_path).resolve().as_posix()}"
    timeline_html_value = build_timeline_html(video_src)

    return (
        local_video_path,
        captions,
        gr.update(visible=True),
        timeline_html_value,
        "↺ Restored your previous session.",
        gr.update(interactive=True),
    )


with gr.Blocks(title="Video Captioning Tool") as demo:
    gr.Markdown(
        "# 🎬 Video Captioning Tool\n"
        "Upload a video, tune how your captions look, and export a fully captioned version.",
        elem_id="header",
    )

    with gr.Row():
        with gr.Column(scale=1):
            video_input = gr.File(
                label="Upload your video",
                file_types=["video"],
                file_count="single",
            )

            with gr.Row():
                orientation = gr.Radio(
                    choices=["Vertical (1080x1920)", "Horizontal (1920x1080)"],
                    value=DEFAULTS["orientation"],
                    label="Output orientation",
                )
                position = gr.Radio(
                    choices=["Top", "Center", "Bottom-third"],
                    value=DEFAULTS["position"],
                    label="Caption position",
                )

            with gr.Accordion("🎨 Caption style", open=True):
                with gr.Row():
                    font = gr.Dropdown(
                        choices=["Montserrat", "Poppins", "Inter", "Bebas Neue"],
                        value=DEFAULTS["font"],
                        label="Font",
                    )
                    font_size = gr.Slider(
                        minimum=30, maximum=140, value=DEFAULTS["font_size"], step=2,
                        label="Font size",
                        info="Size in pixels at 1920px-wide output",
                    )

                with gr.Row():
                    text_color = gr.ColorPicker(value=DEFAULTS["text_color"], label="Text color")
                    stroke_color = gr.ColorPicker(value=DEFAULTS["stroke_color"], label="Outline color")
                    stroke_enabled = gr.Checkbox(value=DEFAULTS["stroke_enabled"], label="Show outline")

                with gr.Row():
                    background = gr.Dropdown(
                        choices=list(BACKGROUND_MAP.keys()),
                        value=DEFAULTS["background"],
                        label="Background style",
                    )
                    animation = gr.Dropdown(
                        choices=list(ANIMATION_MAP.keys()),
                        value=DEFAULTS["animation"],
                        label="Animation style",
                        info="The caption timeline's preview now plays this animation live",
                    )

                pop_intensity = gr.Slider(
                    minimum=0, maximum=100, value=DEFAULTS["pop_intensity"], step=5,
                    label="Pop intensity",
                    info="How dramatic the pop-in is (Pop / scale animation only) — 0 is subtle, 100 is a big bounce",
                )

                reset_btn = gr.Button("↺ Reset style to defaults", size="sm")

            transcribe_btn = gr.Button("1. Transcribe", variant="primary", interactive=False)
            render_btn = gr.Button("2. Render Video", variant="primary", interactive=False)
            gr.Markdown(
                "Tip: style changes apply automatically — after tweaking font/colors/etc, "
                "just click **Render Video** again, no need to re-transcribe.",
                elem_id="style-tip",
            )
            start_over_btn = gr.Button("↺ Start Over", size="sm")
            status_text = gr.Markdown("", elem_id="status-text")

        with gr.Column(scale=1):
            gr.Markdown("### Live style preview")
            preview = gr.HTML(elem_id="preview-box")

    with gr.Group(visible=False) as timeline_group:
        gr.Markdown("### Caption timeline")
        timeline_html = gr.HTML()

    gr.Markdown("### Output")
    output_video = gr.Video(label="Captioned output")

    local_video_state = gr.State()
    hidden_captions = gr.JSON(visible=False)
    hidden_prefs_trigger = gr.JSON(visible=False)
    hidden_session_trigger = gr.JSON(visible=False)

    style_inputs = [
        orientation, position, font, font_size,
        text_color, stroke_color, stroke_enabled, background,
    ]
    style_lock_targets = style_inputs + [animation, pop_intensity, reset_btn]

    def lock_style_controls():
        return [gr.update(interactive=False)] * len(style_lock_targets)

    def unlock_style_controls():
        return [gr.update(interactive=True)] * len(style_lock_targets)

    for control in style_inputs:
        control.change(fn=build_preview_html, inputs=style_inputs, outputs=preview)
        control.change(fn=None, inputs=style_inputs, outputs=[], js=STYLE_SYNC_JS)

    for control in [animation, pop_intensity]:
        control.change(fn=None, inputs=[animation, pop_intensity], outputs=[], js=ANIMATION_SYNC_JS)

    video_input.change(
        fn=lambda f: gr.update(interactive=f is not None),
        inputs=video_input,
        outputs=transcribe_btn,
    )

    reset_btn.click(
        fn=reset_style,
        outputs=[font, font_size, text_color, stroke_color, stroke_enabled, background, animation, pop_intensity],
    )

    start_over_btn.click(
        fn=start_over,
        inputs=[local_video_state],
        outputs=[
            local_video_state,
            hidden_captions,
            timeline_group,
            timeline_html,
            video_input,
            transcribe_btn,
            render_btn,
            output_video,
            status_text,
        ],
    ).then(
        fn=None,
        js="() => { localStorage.removeItem('caption_session'); }",
    )

    transcribe_btn.click(
        fn=show_transcribing_status,
        outputs=[transcribe_btn, status_text],
    ).then(
        fn=lock_style_controls,
        outputs=style_lock_targets,
    ).then(
        fn=run_transcription,
        inputs=[video_input, local_video_state],
        outputs=[local_video_state, hidden_captions, timeline_group, timeline_html, status_text, render_btn],
    ).then(
        fn=lambda: gr.update(interactive=True),
        outputs=transcribe_btn,
    ).then(
        fn=unlock_style_controls,
        outputs=style_lock_targets,
    )

    hidden_captions.change(
        fn=None,
        inputs=[hidden_captions],
        outputs=[],
        js=SAVE_SESSION_JS,
    )

    render_btn.click(
        fn=show_rendering_status,
        outputs=[render_btn, status_text],
    ).then(
        fn=lock_style_controls,
        outputs=style_lock_targets,
    ).then(
        fn=run_render,
        inputs=[
            local_video_state,
            hidden_captions,
            orientation,
            position,
            font,
            font_size,
            text_color,
            stroke_color,
            stroke_enabled,
            background,
            animation,
            pop_intensity,
        ],
        outputs=[output_video, status_text],
        js="""(local_video, captions, orientation, position, font, font_size,
               text_color, stroke_color, stroke_enabled, background, animation, popIntensity) => {
            const collected = window.__collectCaptionTimeline ? window.__collectCaptionTimeline() : null;
            const finalCaptions = collected !== null ? collected : captions;
            return [local_video, finalCaptions, orientation, position, font, font_size,
                    text_color, stroke_color, stroke_enabled, background, animation, popIntensity];
        }""",
    ).then(
        fn=lambda: gr.update(interactive=True),
        outputs=render_btn,
    ).then(
        fn=unlock_style_controls,
        outputs=style_lock_targets,
    )

    demo.load(fn=build_preview_html, inputs=style_inputs, outputs=preview)
    demo.load(fn=None, js=TIMELINE_LOAD_JS)
    demo.load(
        fn=restore_preferences,
        inputs=[hidden_prefs_trigger],
        outputs=style_inputs + [animation, pop_intensity],
        js=RESTORE_PREFS_JS,
    ).then(fn=build_preview_html, inputs=style_inputs, outputs=preview)
    demo.load(
        fn=restore_session,
        inputs=[hidden_session_trigger],
        outputs=[local_video_state, hidden_captions, timeline_group, timeline_html, status_text, render_btn],
        js=RESTORE_SESSION_JS,
    )

if __name__ == "__main__":
    demo.launch(theme=gr.themes.Soft(), css=CUSTOM_CSS)
