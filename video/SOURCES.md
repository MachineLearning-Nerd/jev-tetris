# Video sources

Research checked 2026-09-17. The video uses these public sources for the
definition, primitives, and examples. The animation and Tetris story are
original to this repository.

## Primary sources

- [Introducing System One Models and Jev — TypeSafe AI](https://typesafe.ai/blog/introducing-system-one-models-and-jev)
  - Jev is presented as a System One model that maps state to typed,
    probabilistic decisions.
  - The post describes Choice, Score, and Noul-style decisions and names the
    Doom and Wikiracing examples.
- [TypeSafe AI](https://typesafe.ai/)
  - Product framing: decisions, not strings; confidence can be used to
    automate clear cases and escalate uncertain ones.
- [State — TypeSafe documentation](https://docs.typesafe.ai/concepts/state.md)
  - State can be a string, object, or array; object state is useful for named
    context.
- [Python SDK — TypeSafe documentation](https://docs.typesafe.ai/sdk/python.md)
  - The SDK examples show `system_one` questions returning typed `Choice`,
    `Score`, and `Noul` results.

## Additional public context

- [Jev on AI Gateway — Vercel changelog](https://vercel.com/changelog/typesafe-ai-jev-now-available-on-ai-gateway)
  - Publicly describes Jev as a typed Choice, Score, and Boolean decision
    model, plus routing, verification, and real-time use cases.
- [Jevlike — GitHub](https://github.com/vinnylarouge/jevlike)
  - An independent, Jev-inspired starter model. It is not presented in the
    video as TypeSafe’s model or an official TypeSafe project.

## Editorial boundary

The film deliberately does not state TypeSafe’s performance, pricing, or
“cannot hallucinate” marketing claims as independent facts. It shows the
interface and the use-case pattern, which are the useful ideas for a short
social explainer.
