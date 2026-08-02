import gradio as gr
from run_pipeline import generate_captioned_video

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
)

CUSTOM_CSS = """
#header { text-align: center; margin-bottom: 0.5rem; }
#preview-box { display: flex; justify-content: center; padding: 0.5rem 0; }
#status-text { min-height: 1.5em; }
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
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Montserrat:wght@700&family=Poppins:wght@700&family=Inter:wght@700&family=Bebas+Neue&display=swap');
    </style>
    <div style="width:{preview_width}px;height:{preview_height}px;background:#111;
                display:flex;justify-content:center;{position_css}
                border-radius:10px;overflow:hidden;border:1px solid #333;">
      <div style="font-family:'{font}',sans-serif;font-size:{scaled_font_size}px;font-weight:700;
                  color:{text_color};{stroke_css}{bg_css}text-align:center;max-width:90%;line-height:1.2;">
        {sample_text}
      </div>
    </div>
    """


def process_video(
    video_path,
    orientation_label,
    position_label,
    font,
    font_size,
    text_color,
    stroke_color,
    stroke_enabled,
    background_label,
    animation_label,
):
    if not video_path:
        return gr.update(), "⚠️ Please upload a video first."

    orientation = "vertical" if orientation_label.startswith("Vertical") else "horizontal"

    caption_style = {
        "fontFamily": font,
        "fontSize": font_size,
        "textColor": text_color,
        "strokeColor": stroke_color,
        "strokeEnabled": stroke_enabled,
        "background": BACKGROUND_MAP[background_label],
        "animation": ANIMATION_MAP[animation_label],
    }

    try:
        output_path = generate_captioned_video(
            video_path,
            orientation,
            POSITION_MAP[position_label],
            caption_style,
        )
    except Exception as e:
        return gr.update(), f"❌ Something went wrong: {e}"

    return output_path, "✅ Done! Your captioned video is ready below."


def show_processing_status():
    return gr.update(interactive=False), "⏳ Processing... this can take a few minutes depending on video length."


def finish_processing():
    return gr.update(interactive=True)


def reset_style():
    return (
        DEFAULTS["font"],
        DEFAULTS["font_size"],
        DEFAULTS["text_color"],
        DEFAULTS["stroke_color"],
        DEFAULTS["stroke_enabled"],
        DEFAULTS["background"],
        DEFAULTS["animation"],
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
                        info="Preview shows style only — animation plays in the rendered video",
                    )

                reset_btn = gr.Button("↺ Reset style to defaults", size="sm")

            generate_btn = gr.Button("Generate Captions", variant="primary", interactive=False)
            status_text = gr.Markdown("", elem_id="status-text")

        with gr.Column(scale=1):
            gr.Markdown("### Live style preview")
            preview = gr.HTML(elem_id="preview-box")

            gr.Markdown("### Output")
            output_video = gr.Video(label="Captioned output")

    style_inputs = [
        orientation, position, font, font_size,
        text_color, stroke_color, stroke_enabled, background,
    ]
    for control in style_inputs:
        control.change(fn=build_preview_html, inputs=style_inputs, outputs=preview)

    video_input.change(
        fn=lambda f: gr.update(interactive=f is not None),
        inputs=video_input,
        outputs=generate_btn,
    )

    reset_btn.click(
        fn=reset_style,
        outputs=[font, font_size, text_color, stroke_color, stroke_enabled, background, animation],
    )

    generate_btn.click(
        fn=show_processing_status,
        outputs=[generate_btn, status_text],
    ).then(
        fn=process_video,
        inputs=[
            video_input,
            orientation,
            position,
            font,
            font_size,
            text_color,
            stroke_color,
            stroke_enabled,
            background,
            animation,
        ],
        outputs=[output_video, status_text],
    ).then(
        fn=finish_processing,
        outputs=generate_btn,
    )

    demo.load(fn=build_preview_html, inputs=style_inputs, outputs=preview)

if __name__ == "__main__":
    demo.launch(theme=gr.themes.Soft(), css=CUSTOM_CSS)
