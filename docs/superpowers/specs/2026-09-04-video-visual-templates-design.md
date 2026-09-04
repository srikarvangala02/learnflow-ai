# Video Visual Templates Design (Tier 1)

**Date:** 2026-09-04
**Scope:** Give Claude a small fixed library of visual slide templates it can choose from during script generation, so slides can show an animated curve plot, bar chart, diagram, or annotated formula instead of only title+bullets. Explicitly excludes narration referencing animation timing/checkpoints and any visual type beyond the four defined here — both deferred to a later phase.

---

## 1. Goal

Today every slide is `title` + `narration` + `bullets`, rendered by one `Slide.tsx` component. This design adds four additional slide types Claude can choose per-slide when content has real quantitative or structural shape — a function/trend, a categorical comparison, a spatial/relational structure, or a single equation worth breaking down — while keeping `bullets` as the default and the universal fallback.

---

## 2. Files

**Create:**
- `render/src/visuals/CurvePlot.tsx`
- `render/src/visuals/BarChart.tsx`
- `render/src/visuals/Diagram.tsx`
- `render/src/visuals/FormulaHighlight.tsx`
- `render/src/visuals/VisualErrorBoundary.tsx`
- `backend/tests/test_visual_validation.py`

**Modify:**
- `backend/script_generator.py` — extend `_USER_TEMPLATE` schema/rules; add post-parse validation/sanitization pass
- `backend/requirements.txt` — no new Python deps (pydantic already present transitively via fastapi)
- `render/package.json` — add `katex` dependency
- `render/src/LearnFlowVideo.tsx` — extend `SlideData` with `type`/`visual`
- `render/src/Slide.tsx` — becomes a dispatcher on `slide.type`
- `render/src/Root.tsx` — placeholder default slide gets `type: "bullets"`

---

## 3. Template Data Shapes

All four live under a slide's optional `visual` field (see §4). Claude generates real sampled data, never symbolic expressions or code — this keeps every Remotion component a pure, dumb renderer with no math evaluation at render time.

### `curve_plot`
```json
{
  "x_label": "x", "y_label": "f(x)",
  "x_min": -5, "x_max": 5,
  "series": [
    {"label": "f(x) = x²", "points": [{"x": -5, "y": 25}, {"x": -4, "y": 16}, "..."]}
  ]
}
```
1–3 series, 8–30 points per series, points ordered by ascending `x`.

### `bar_chart`
```json
{
  "y_label": "Expected Damage ($)",
  "bars": [{"label": "Threat X", "value": 800}, {"label": "Threat Y", "value": 2000}]
}
```
2–6 bars.

### `diagram`
Covers both labeled-relationship diagrams and plain coordinate points with one schema — a node's `shape` can be `"point"` for a bare dot with no label box:
```json
{
  "nodes": [
    {"id": "A", "label": "Sample Space Ω", "x": 50, "y": 30, "shape": "circle"},
    {"id": "B", "label": "Event A", "x": 30, "y": 60, "shape": "rect"}
  ],
  "edges": [{"from": "A", "to": "B", "label": "contains"}]
}
```
`x`/`y` are normalized 0–100 (percentage of canvas). `shape` is `"circle" | "rect" | "point"`. 2–6 nodes, 0–5 edges. Every `edge.from`/`edge.to` must reference an existing node `id`.

### `formula`
LaTeX rendered via KaTeX, with sub-expressions wrapped in `\htmlId{}{}` so annotation leader-lines target exact rendered spans instead of fuzzy-matching substrings after the fact:
```json
{
  "latex": "\\htmlId{term-mean}{E[X]} = \\sum_{i} \\htmlId{term-outcome}{x_i} \\htmlId{term-prob}{P(x_i)}",
  "annotations": [
    {"id": "term-mean", "label": "Expected value"},
    {"id": "term-outcome", "label": "Each outcome"},
    {"id": "term-prob", "label": "Its probability"}
  ]
}
```
1–4 annotations. Every `annotation.id` must appear as an `\htmlId{...}` in `latex`.

**KaTeX trust scope:** `\htmlId`/`\htmlClass` require KaTeX's `trust` option. Since `latex` is model-generated from user-uploaded PDF content — not fully trusted input — `trust` is scoped to a predicate allowing only `\htmlId`/`\htmlClass`, not `trust: true` (which would also enable `\href` and other riskier commands):
```ts
trust: (context) => context.command === '\\htmlId' || context.command === '\\htmlClass'
```

---

## 4. Schema Changes

Every slide keeps `bullets`, regardless of `type` — this is what makes the fallback in §6 free: no separate fallback-content synthesis path is ever needed.

```json
{
  "index": 0,
  "title": "...",
  "narration": "...",
  "bullets": ["...", "..."],
  "type": "bullets" | "curve_plot" | "bar_chart" | "diagram" | "formula",
  "visual": { "...": "template-specific shape from §3" }
}
```
`visual` is absent (or ignored if present) when `type == "bullets"`. `narration` and TTS synthesis (`tts_generator.py`) are untouched by this design.

---

## 5. Prompt Changes (`backend/script_generator.py`)

`_USER_TEMPLATE` gains: the four `visual` schemas from §3, and explicit per-type trigger conditions so Claude picks a type based on what the content actually is, not novelty:

- `curve_plot` — content describes a function, growth/decay pattern, or distribution over a continuous variable
- `bar_chart` — content compares named discrete quantities
- `diagram` — content describes spatial, relational, or set structure between named entities
- `formula` — the slide centers on one named equation worth breaking into parts
- `bullets` — default; used whenever content is conceptual, definitional, or qualitative and doesn't clearly fit one of the above

Explicit anti-overuse rule: no more than half the deck should use a non-`bullets` type — visuals earn their place per-slide, not as decoration.

---

## 6. Validation & Fallback

Two independent layers. The primary layer should catch nearly everything; the backstop exists because a multi-minute render dying over one bad slide is a much worse failure than one slide silently degrading to bullets.

### Primary — Python, `backend/script_generator.py`

Immediately after `generate_script()`'s JSON parses (before the script is written to disk or handed to TTS), a new validation pass runs over `script["slides"]`. For each slide where `type != "bullets"`, its `visual` is validated against a pydantic model matching that type's shape from §3 (field presence, count bounds, and for `diagram`, that every edge references a real node id; for `formula`, that every annotation id appears in the LaTeX).

On any validation failure — unrecognized `type`, missing `visual`, or a shape mismatch — that slide's `type` is rewritten to `"bullets"` and `visual` is dropped. `bullets` is already present on every slide, so nothing is lost. Logged as a warning (slide index + reason), not fatal — this is a distinct, non-fatal, per-slide failure mode from the existing whole-script JSON-retry logic in `generate_script`, which handles "not valid JSON at all."

### Backstop — TypeScript, `render/src/visuals/VisualErrorBoundary.tsx`

Each visual component is wrapped in a React Error Boundary. If a runtime error occurs inside a visual component despite passing Python-side validation (e.g., a shape-valid but pathological value like `NaN` triggering a bad SVG path at render time), the boundary catches it and renders that slide's `title` + `bullets` in the existing plain layout instead of letting the error propagate and kill the entire Remotion render process.

---

## 7. Remotion Components

`render/src/visuals/`, one file per template — pure SVG, animated via `interpolate`/`spring` off `useCurrentFrame()`. No charting library: keeps the render image light and gives full animation control, consistent with `Slide.tsx`'s existing hand-styled approach. Palette matches `frontend/tailwind.config.js` exactly: background `#1a1a2e`, primary accent `#7c3aed`, secondary series color `#22c55e`, text `#e0e0ff`/`#c0c0e0`.

Shared motion language across templates:
- Structural elements (axes, node shapes, bar outlines) reveal via staggered `spring`
- Lines/curves/edges draw in via the stroke-dasharray/dashoffset technique (`interpolate(frame, [start, end], [totalLength, 0])`)
- `bar_chart` bars grow from 0 to target height via `spring`, staggered per bar by index
- `formula` reveals the full equation first via `spring`, then each annotation's label + leader-line staggers in afterward so the viewer's eye follows equation → parts

`Slide.tsx` becomes a `switch` on `slide.type`, dispatching to the matching visual component (each wrapped in `VisualErrorBoundary`) or the existing bullets layout. `SlideData` in `LearnFlowVideo.tsx` gains `type: SlideType` and `visual?: VisualPayload` (discriminated union keyed on `type`). `Root.tsx`'s placeholder `defaultProps` slide gets `type: "bullets"`.

---

## 8. Out of Scope

- Narration referencing specific animation timing/checkpoints within a visual (later phase)
- Any visual type beyond these four
- A 5th "point plot" template — folded into `diagram` via `shape: "point"` per design discussion
- Symbolic function input/evaluation (Claude always supplies sampled points, never expressions)
- Editing/customizing a chosen visual after generation (no UI for this)
- Cross-slide visual consistency enforcement (e.g., matching axis scales across two `curve_plot` slides)
