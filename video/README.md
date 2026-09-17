# Jev explainer video

The rendered social asset is `jev_explainer_landscape.mp4`. It now includes a
calm Kokoro narration aligned to the scene timings; the source voiceover is
`jev_explainer_narration.wav`.

The Tetris section uses screenshots captured from the running Streamlit app in
automatic mode. The capture sequence is kept in `real_tetris/` so the video can
be regenerated without replacing the real gameplay with an illustration.

Generate the narration in a temporary environment with Kokoro 0.9.4, then
render the video with the narration:

```sh
/tmp/jev-video-venv/bin/python video/generate_jev_voiceover.py
python3 video/render_jev_explainer_landscape.py --audio video/jev_explainer_narration.wav
```

Render a silent version by omitting `--audio`:

```sh
python3 video/render_jev_explainer_landscape.py
```

The renderer writes the MP4 through `ffmpeg` and also creates a poster frame at
`video/jev_explainer_landscape_poster.png`. It needs Python Pillow and a local
`ffmpeg`. Kokoro is only needed when regenerating the narration; it is not a
runtime dependency of the Tetris app.

The full timing and suggested post copy are in
[`jev_explainer_script.md`](jev_explainer_script.md). Claims and links are in
[`SOURCES.md`](SOURCES.md).
