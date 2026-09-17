"""Generate the calm Kokoro narration for the Jev explainer."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import soundfile as sf
from kokoro import KPipeline


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "video" / "jev_explainer_narration.wav"
VOICE = "af_heart"
SPEED = 0.92
SAMPLE_RATE = 24_000
DURATION = 55.0

SEGMENTS = [
    (0.0, 4.7, "Most AI writes. Jev decides."),
    (
        4.7,
        12.5,
        "Give it application state and a typed question. Jev returns a constrained judgment that code can use.",
    ),
    (
        12.5,
        20.0,
        "A choice. A score. A probability. Small AI primitives for routing, ranking, and verification.",
    ),
    (
        20.0,
        34.0,
        "Here, the state is a real Tetris board. Jev chooses a legal placement. Python verifies it, and the game owns the physics.",
    ),
    (
        34.0,
        43.0,
        "The same pattern fits any loop that needs a decision: route, rank, verify, react.",
    ),
    (
        43.0,
        49.5,
        "Doom and Wikiracing already show the pattern. This demo makes the loop visible.",
    ),
    (
        49.5,
        55.0,
        "Jev is not a chatbot. It is a decision layer for software.",
    ),
]


def generate_segment(pipeline: KPipeline, content: str) -> np.ndarray:
    chunks = []
    for _, _, audio in pipeline(content, voice=VOICE, speed=SPEED, split_pattern=r"\n+"):
        if hasattr(audio, "detach"):
            audio = audio.detach().cpu().numpy()
        chunks.append(np.asarray(audio, dtype=np.float32).reshape(-1))
    if not chunks:
        raise RuntimeError(f"Kokoro returned no audio for: {content}")
    return np.concatenate(chunks)


def add_fade(audio: np.ndarray) -> np.ndarray:
    faded = audio.copy()
    fade_samples = min(int(SAMPLE_RATE * 0.04), len(faded) // 2)
    if fade_samples == 0:
        return faded
    faded[:fade_samples] *= np.linspace(0.0, 1.0, fade_samples, dtype=np.float32)
    faded[-fade_samples:] *= np.linspace(1.0, 0.0, fade_samples, dtype=np.float32)
    return faded


def render_voiceover() -> None:
    pipeline = KPipeline(lang_code="a")
    timeline = np.zeros(round(DURATION * SAMPLE_RATE), dtype=np.float32)
    for start, end, content in SEGMENTS:
        audio = add_fade(generate_segment(pipeline, content))
        slot_samples = round((end - start) * SAMPLE_RATE)
        if len(audio) > slot_samples:
            seconds = len(audio) / SAMPLE_RATE
            raise RuntimeError(
                f"Narration is too long for {start:.1f}-{end:.1f}s: {seconds:.2f}s"
            )
        offset = round(start * SAMPLE_RATE)
        timeline[offset : offset + len(audio)] += audio

    peak = float(np.max(np.abs(timeline)))
    if peak > 0.95:
        timeline *= 0.95 / peak
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    sf.write(OUTPUT, timeline, SAMPLE_RATE, subtype="PCM_16")
    print(f"wrote {OUTPUT}")
    print(f"voice={VOICE} speed={SPEED} duration={DURATION:.1f}s")


if __name__ == "__main__":
    render_voiceover()
