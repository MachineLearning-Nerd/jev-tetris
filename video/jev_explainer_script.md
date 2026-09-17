# Jev explainer video

Format: 1920 × 1080, 30 fps, 55 seconds, narrated caption-led landscape video.

The captions remain self-contained so the video can be posted with or without
voiceover. Claims are phrased conservatively: the video explains
the interface and the published examples without repeating vendor benchmark
numbers as if they were independent measurements.

## Timeline

| Time | On-screen story |
| --- | --- |
| 0:00–0:04.7 | “Most AI writes. Jev decides.” A quick definition of the category. |
| 0:04.7–0:13.3 | State flows into Jev; a typed judgment comes out. The answer space is declared by the app. |
| 0:13.3–0:21 | Choice, Score, and Noul show the three useful decision shapes. |
| 0:20–0:34 | Real Tetris app capture: the board, queue, score, auto mode, and changing placements are visible as the game plays. |
| 0:33–0:42.8 | Use cases: route, rank, verify, and react. |
| 0:42.8–0:49.6 | Public TypeSafe examples: Doom and Wikiracing. The Tetris experiment adds a transparent, inspectable game loop. |
| 0:49.6–0:55 | “Jev is not a chatbot. It’s a decision layer.” |

## Narration

The voiceover uses Kokoro `af_heart` at speed `0.92`, with each block aligned
to the scene it describes. The script is intentionally about 100 words so a
calm delivery leaves room for the board and placements to be understood.

> Most AI writes. Jev decides.
>
> Give it application state and a typed question. Jev returns a constrained
> judgment that code can use.
>
> A choice. A score. A probability. Small AI primitives for routing, ranking,
> and verification.
>
> Here, the state is a real Tetris board. Jev chooses a legal placement.
> Python verifies it, and the game owns the physics.
>
> The same pattern fits any loop that needs a decision: route, rank, verify,
> react.
>
> Doom and Wikiracing already show the pattern. This demo makes the loop
> visible.
>
> Jev is not a chatbot. It is a decision layer for software.

## Suggested post copy

Most AI is optimized to write.

Jev is optimized to judge.

Give it state plus typed questions. Get back a Choice, Score, or Noul with a
probability your code can use.

This Tetris demo makes the pattern visible: Jev selects a legal placement,
Python verifies it, and the game owns the physics.

That is the interesting shift: AI as a decision primitive, not just a chat box.

## Accuracy notes

- Jev is described as TypeSafe’s early-access System One decision model.
- The video says “typed judgment,” not “perfect judgment.” A schema constrains
  the shape of the output; it does not make the model infallible.
- Doom and Wikiracing are labeled as TypeSafe examples. Tetris is labeled as
  this repository’s experiment.
- No company data, private data, speed multiplier, pricing claim, or claim of
  independent benchmark validation is used in the film.
