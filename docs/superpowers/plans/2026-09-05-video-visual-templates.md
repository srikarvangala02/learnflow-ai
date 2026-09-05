# Video Visual Templates Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let Claude choose, per slide, between the existing bullets layout and one of four new visual templates (curve plot, bar chart, diagram, annotated formula), each populated with real data during script generation and rendered as an animated Remotion component.

**Architecture:** Backend gains a pydantic-validated `visual` payload per template plus a sanitization pass that silently downgrades any malformed visual slide to `bullets` before it ever reaches TTS or the renderer. Render side gains one SVG/React component per template plus a dispatcher in `Slide.tsx` that switches on `slide.type`, each visual wrapped in a React Error Boundary as a second, independent line of defense.

**Tech Stack:** Python (pydantic v2, already present via fastapi), TypeScript/React (Remotion 4, `interpolate`/`spring`), KaTeX for formula rendering.

**Spec:** `docs/superpowers/specs/2026-09-04-video-visual-templates-design.md`

## Global Constraints

- Palette must match `frontend/tailwind.config.js` exactly: background `#1a1a2e`, primary accent `#7c3aed`, secondary series color `#22c55e`, text `#e0e0ff` (primary) / `#c0c0e0` (secondary)
- No new Python dependencies — pydantic is already present transitively via fastapi
- No charting library in `render/` — every visual is pure SVG animated with Remotion's `interpolate`/`spring` only
- KaTeX `trust` must be scoped to a predicate allowing only `\htmlId`/`\htmlClass` — never `trust: true`
- Every slide always includes `bullets`, regardless of `type` — this is what makes the fallback free
- No more than half of a deck's slides should use a non-`bullets` type (prompt-level guidance, not code-enforced)

---

### Task 1: Pydantic visual validation models

**Files:**
- Modify: `backend/script_generator.py` (add imports + models near the top, after existing imports)
- Test: `backend/tests/test_visual_validation.py` (new file)

**Interfaces:**
- Produces: `CurvePlotVisual`, `BarChartVisual`, `DiagramVisual`, `FormulaVisual` (pydantic `BaseModel` subclasses), and `_VISUAL_MODELS: dict[str, type[BaseModel]]` mapping `"curve_plot"|"bar_chart"|"diagram"|"formula"` to its model class. Task 2 imports `_VISUAL_MODELS` from `script_generator`.

- [ ] **Step 1: Write the failing tests**

```python
# backend/tests/test_visual_validation.py
import pytest
from pydantic import ValidationError

from script_generator import (
    CurvePlotVisual,
    BarChartVisual,
    DiagramVisual,
    FormulaVisual,
    _VISUAL_MODELS,
)


def test_curve_plot_accepts_valid_data():
    CurvePlotVisual.model_validate({
        "x_label": "x", "y_label": "f(x)", "x_min": -5, "x_max": 5,
        "series": [{"label": "f(x) = x^2", "points": [{"x": i, "y": i * i} for i in range(10)]}],
    })


def test_curve_plot_rejects_too_few_points():
    with pytest.raises(ValidationError):
        CurvePlotVisual.model_validate({
            "x_label": "x", "y_label": "f(x)", "x_min": -5, "x_max": 5,
            "series": [{"label": "f(x)", "points": [{"x": 0, "y": 0}]}],
        })


def test_curve_plot_rejects_too_many_series():
    series = [{"label": f"s{i}", "points": [{"x": j, "y": j} for j in range(8)]} for i in range(4)]
    with pytest.raises(ValidationError):
        CurvePlotVisual.model_validate({"x_label": "x", "y_label": "y", "x_min": 0, "x_max": 1, "series": series})


def test_bar_chart_accepts_valid_data():
    BarChartVisual.model_validate({"y_label": "Value", "bars": [{"label": "A", "value": 1}, {"label": "B", "value": 2}]})


def test_bar_chart_rejects_single_bar():
    with pytest.raises(ValidationError):
        BarChartVisual.model_validate({"y_label": "Value", "bars": [{"label": "A", "value": 1}]})


def test_diagram_accepts_valid_nodes_and_edges():
    DiagramVisual.model_validate({
        "nodes": [
            {"id": "A", "label": "Sample Space", "x": 50, "y": 30, "shape": "circle"},
            {"id": "B", "label": "Event A", "x": 30, "y": 60, "shape": "rect"},
        ],
        "edges": [{"from": "A", "to": "B", "label": "contains"}],
    })


def test_diagram_rejects_edge_referencing_unknown_node():
    with pytest.raises(ValidationError):
        DiagramVisual.model_validate({
            "nodes": [
                {"id": "A", "label": "A", "x": 50, "y": 30, "shape": "circle"},
                {"id": "B", "label": "B", "x": 30, "y": 60, "shape": "circle"},
            ],
            "edges": [{"from": "A", "to": "does-not-exist"}],
        })


def test_diagram_rejects_single_node():
    with pytest.raises(ValidationError):
        DiagramVisual.model_validate({"nodes": [{"id": "A", "label": "A", "x": 50, "y": 50, "shape": "point"}], "edges": []})


def test_formula_accepts_valid_data():
    FormulaVisual.model_validate({
        "latex": "\\htmlId{a}{E[X]} = \\htmlId{b}{x}",
        "annotations": [{"id": "a", "label": "Expected value"}, {"id": "b", "label": "Outcome"}],
    })


def test_formula_rejects_annotation_id_missing_from_latex():
    with pytest.raises(ValidationError):
        FormulaVisual.model_validate({
            "latex": "\\htmlId{a}{E[X]}",
            "annotations": [{"id": "a", "label": "Expected value"}, {"id": "missing", "label": "Nope"}],
        })


def test_visual_models_registry_has_all_four_types():
    assert set(_VISUAL_MODELS.keys()) == {"curve_plot", "bar_chart", "diagram", "formula"}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && pytest tests/test_visual_validation.py -v`
Expected: FAIL with `ImportError: cannot import name 'CurvePlotVisual'` (the models don't exist yet).

- [ ] **Step 3: Implement the models**

Add to `backend/script_generator.py`, after the existing imports (`import json`, `import os`, `from pathlib import Path`, `import anthropic`, `import pdfplumber`):

```python
import logging
from typing import Literal

from pydantic import BaseModel, Field, ValidationError, field_validator, model_validator

logger = logging.getLogger(__name__)


class CurvePoint(BaseModel):
    x: float
    y: float


class CurveSeries(BaseModel):
    label: str
    points: list[CurvePoint]

    @field_validator("points")
    @classmethod
    def _check_point_count(cls, v: list[CurvePoint]) -> list[CurvePoint]:
        if not (8 <= len(v) <= 30):
            raise ValueError("points must have between 8 and 30 entries")
        return v


class CurvePlotVisual(BaseModel):
    x_label: str
    y_label: str
    x_min: float
    x_max: float
    series: list[CurveSeries]

    @field_validator("series")
    @classmethod
    def _check_series_count(cls, v: list[CurveSeries]) -> list[CurveSeries]:
        if not (1 <= len(v) <= 3):
            raise ValueError("series must have between 1 and 3 entries")
        return v


class Bar(BaseModel):
    label: str
    value: float


class BarChartVisual(BaseModel):
    y_label: str
    bars: list[Bar]

    @field_validator("bars")
    @classmethod
    def _check_bar_count(cls, v: list[Bar]) -> list[Bar]:
        if not (2 <= len(v) <= 6):
            raise ValueError("bars must have between 2 and 6 entries")
        return v


class DiagramNode(BaseModel):
    id: str
    label: str
    x: float
    y: float
    shape: Literal["circle", "rect", "point"]


class DiagramEdge(BaseModel):
    from_: str = Field(alias="from")
    to: str
    label: str | None = None

    model_config = {"populate_by_name": True}


class DiagramVisual(BaseModel):
    nodes: list[DiagramNode]
    edges: list[DiagramEdge] = []

    @field_validator("nodes")
    @classmethod
    def _check_node_count(cls, v: list[DiagramNode]) -> list[DiagramNode]:
        if not (2 <= len(v) <= 6):
            raise ValueError("nodes must have between 2 and 6 entries")
        return v

    @field_validator("edges")
    @classmethod
    def _check_edge_count(cls, v: list[DiagramEdge]) -> list[DiagramEdge]:
        if len(v) > 5:
            raise ValueError("edges must have at most 5 entries")
        return v

    @model_validator(mode="after")
    def _check_edges_reference_nodes(self) -> "DiagramVisual":
        node_ids = {n.id for n in self.nodes}
        for edge in self.edges:
            if edge.from_ not in node_ids or edge.to not in node_ids:
                raise ValueError(f"edge references unknown node id (from={edge.from_!r}, to={edge.to!r})")
        return self


class FormulaAnnotation(BaseModel):
    id: str
    label: str


class FormulaVisual(BaseModel):
    latex: str
    annotations: list[FormulaAnnotation]

    @field_validator("annotations")
    @classmethod
    def _check_annotation_count(cls, v: list[FormulaAnnotation]) -> list[FormulaAnnotation]:
        if not (1 <= len(v) <= 4):
            raise ValueError("annotations must have between 1 and 4 entries")
        return v

    @model_validator(mode="after")
    def _check_annotation_ids_in_latex(self) -> "FormulaVisual":
        for ann in self.annotations:
            if f"\\htmlId{{{ann.id}}}" not in self.latex:
                raise ValueError(f"annotation id {ann.id!r} not found in latex")
        return self


_VISUAL_MODELS: dict[str, type[BaseModel]] = {
    "curve_plot": CurvePlotVisual,
    "bar_chart": BarChartVisual,
    "diagram": DiagramVisual,
    "formula": FormulaVisual,
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && pytest tests/test_visual_validation.py -v`
Expected: PASS (12 tests)

- [ ] **Step 5: Commit**

```bash
git add backend/script_generator.py backend/tests/test_visual_validation.py
git commit -m "feat: add pydantic validation models for visual slide templates

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

### Task 2: Sanitization pass

**Files:**
- Modify: `backend/script_generator.py`
- Test: `backend/tests/test_visual_validation.py`

**Interfaces:**
- Consumes: `_VISUAL_MODELS` from Task 1
- Produces: `_sanitize_slide_types(slides: list[dict]) -> list[dict]`. Task 3 calls this from `generate_script`.

- [ ] **Step 1: Write the failing tests**

Append to `backend/tests/test_visual_validation.py`:

```python
from script_generator import _sanitize_slide_types


def test_sanitize_leaves_valid_visual_slide_untouched():
    slides = [{
        "index": 0, "title": "T", "narration": "N", "bullets": ["a", "b"],
        "type": "bar_chart",
        "visual": {"y_label": "V", "bars": [{"label": "A", "value": 1}, {"label": "B", "value": 2}]},
    }]
    result = _sanitize_slide_types(slides)
    assert result[0]["type"] == "bar_chart"
    assert result[0]["visual"]["bars"][0]["label"] == "A"


def test_sanitize_falls_back_invalid_visual_to_bullets():
    slides = [{
        "index": 0, "title": "T", "narration": "N", "bullets": ["a", "b"],
        "type": "bar_chart",
        "visual": {"y_label": "V", "bars": [{"label": "Only One", "value": 1}]},
    }]
    result = _sanitize_slide_types(slides)
    assert result[0]["type"] == "bullets"
    assert "visual" not in result[0]
    assert result[0]["bullets"] == ["a", "b"]


def test_sanitize_falls_back_unknown_type_to_bullets():
    slides = [{"index": 0, "title": "T", "narration": "N", "bullets": ["a"], "type": "pie_chart", "visual": {}}]
    result = _sanitize_slide_types(slides)
    assert result[0]["type"] == "bullets"
    assert "visual" not in result[0]


def test_sanitize_leaves_bullets_slide_untouched():
    slides = [{"index": 0, "title": "T", "narration": "N", "bullets": ["a", "b"], "type": "bullets"}]
    result = _sanitize_slide_types(slides)
    assert result[0] == slides[0]


def test_sanitize_defaults_missing_type_to_bullets():
    slides = [{"index": 0, "title": "T", "narration": "N", "bullets": ["a", "b"]}]
    result = _sanitize_slide_types(slides)
    assert result[0]["bullets"] == ["a", "b"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && pytest tests/test_visual_validation.py -v -k sanitize`
Expected: FAIL with `ImportError: cannot import name '_sanitize_slide_types'`

- [ ] **Step 3: Implement the sanitization function**

Add to `backend/script_generator.py`, directly after the `_VISUAL_MODELS` dict from Task 1:

```python
def _sanitize_slide_types(slides: list[dict]) -> list[dict]:
    sanitized = []
    for slide in slides:
        slide_type = slide.get("type", "bullets")
        if slide_type == "bullets":
            sanitized.append(slide)
            continue

        model = _VISUAL_MODELS.get(slide_type)
        if model is None:
            logger.warning("Slide %s has unknown type %r; falling back to bullets", slide.get("index"), slide_type)
            fallback = {k: v for k, v in slide.items() if k != "visual"}
            fallback["type"] = "bullets"
            sanitized.append(fallback)
            continue

        try:
            model.model_validate(slide.get("visual") or {})
            sanitized.append(slide)
        except ValidationError as exc:
            logger.warning("Slide %s visual failed validation (%s); falling back to bullets", slide.get("index"), exc)
            fallback = {k: v for k, v in slide.items() if k != "visual"}
            fallback["type"] = "bullets"
            sanitized.append(fallback)

    return sanitized
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && pytest tests/test_visual_validation.py -v`
Expected: PASS (17 tests total)

- [ ] **Step 5: Commit**

```bash
git add backend/script_generator.py backend/tests/test_visual_validation.py
git commit -m "feat: add sanitization pass that falls back invalid visual slides to bullets

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

### Task 3: Wire sanitization into `generate_script`

**Files:**
- Modify: `backend/script_generator.py:97-108` (the `generate_script` function body, after JSON parsing)
- Test: `backend/tests/test_script_generator.py`

**Interfaces:**
- Consumes: `_sanitize_slide_types` from Task 2

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/test_script_generator.py`:

```python
def test_generate_script_sanitizes_invalid_visual_slide(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

    script_body = {
        "title": "Test Document",
        "slides": [
            {
                "index": 0,
                "title": "Bad Chart",
                "narration": "This has an invalid bar chart.",
                "bullets": ["Point A", "Point B"],
                "type": "bar_chart",
                "visual": {"y_label": "Value", "bars": [{"label": "Only One", "value": 5}]},
            }
        ],
    }
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text=json.dumps(script_body))]

    with patch("script_generator.anthropic.Anthropic") as mock_cls:
        mock_cls.return_value.messages.create.return_value = mock_response
        result = generate_script("file-abc", "some source text")

    assert result["slides"][0]["type"] == "bullets"
    assert "visual" not in result["slides"][0]
    assert result["slides"][0]["bullets"] == ["Point A", "Point B"]


def test_generate_script_keeps_valid_visual_slide(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

    script_body = {
        "title": "Test Document",
        "slides": [
            {
                "index": 0,
                "title": "Good Chart",
                "narration": "This has a valid bar chart.",
                "bullets": ["Point A", "Point B"],
                "type": "bar_chart",
                "visual": {"y_label": "Value", "bars": [{"label": "A", "value": 1}, {"label": "B", "value": 2}]},
            }
        ],
    }
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text=json.dumps(script_body))]

    with patch("script_generator.anthropic.Anthropic") as mock_cls:
        mock_cls.return_value.messages.create.return_value = mock_response
        result = generate_script("file-abc", "some source text")

    assert result["slides"][0]["type"] == "bar_chart"
    assert result["slides"][0]["visual"]["bars"][0]["label"] == "A"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && pytest tests/test_script_generator.py -v -k "sanitizes_invalid or keeps_valid"`
Expected: FAIL — `result["slides"][0]["type"]` raises `KeyError: 'type'` (nothing rewrites the slide yet, and the mock data has `type`/`visual` keys generate_script currently does nothing with, so the invalid one still shows `"type": "bar_chart"` instead of being downgraded).

- [ ] **Step 3: Wire it in**

In `backend/script_generator.py`, `generate_script` currently ends with:

```python
    try:
        script = json.loads(raw)
    except json.JSONDecodeError:
        raw2 = _call([
            user_msg,
            {"role": "assistant", "content": raw},
            {"role": "user", "content": "That was not valid JSON. Return only the JSON object, nothing else."},
        ])
        script = json.loads(raw2)

    script["file_id"] = file_id
    return script
```

Change to:

```python
    try:
        script = json.loads(raw)
    except json.JSONDecodeError:
        raw2 = _call([
            user_msg,
            {"role": "assistant", "content": raw},
            {"role": "user", "content": "That was not valid JSON. Return only the JSON object, nothing else."},
        ])
        script = json.loads(raw2)

    script["slides"] = _sanitize_slide_types(script.get("slides", []))
    script["file_id"] = file_id
    return script
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && pytest tests/test_script_generator.py -v`
Expected: PASS (all tests in the file, including the two new ones)

- [ ] **Step 5: Commit**

```bash
git add backend/script_generator.py backend/tests/test_script_generator.py
git commit -m "feat: sanitize visual slide types inside generate_script

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

### Task 4: Extend the generation prompt with visual template schemas

**Files:**
- Modify: `backend/script_generator.py:46-69` (`_USER_TEMPLATE`)
- Test: `backend/tests/test_script_generator.py`

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/test_script_generator.py`:

```python
def test_user_template_documents_all_visual_types():
    for keyword in ("curve_plot", "bar_chart", "diagram", "formula"):
        assert keyword in _USER_TEMPLATE


def test_user_template_documents_htmlid_convention():
    assert "\\htmlId" in _USER_TEMPLATE


def test_user_template_documents_visual_overuse_rule():
    assert "no more than half" in _USER_TEMPLATE.lower()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && pytest tests/test_script_generator.py -v -k documents`
Expected: FAIL — none of these keywords exist in `_USER_TEMPLATE` yet.

- [ ] **Step 3: Replace `_USER_TEMPLATE`**

Replace the existing `_USER_TEMPLATE` in `backend/script_generator.py` entirely with:

```python
_USER_TEMPLATE = """\
Source text:
{text}

Produce a JSON object with this exact schema:
{{
  "title": "<overall document title>",
  "slides": [
    {{
      "index": <int starting at 0>,
      "title": "<slide title>",
      "narration": "<1-2 short sentences suitable for text-to-speech, speakable in under 12 seconds>",
      "bullets": ["<key point>", ...],
      "type": "<one of: bullets, curve_plot, bar_chart, diagram, formula>",
      "visual": <template-specific object, see below — omit or use {{}} when type is "bullets">
    }}
  ]
}}

Rules:
- Generate between 5 and 8 slides.
- Each slide must have 2 to 4 bullets, regardless of its type — bullets are always required, even for slides with a visual.
- Narration must be complete sentences, not bullet points.
- Narration must be speakable in under 12 seconds at a natural pace — roughly 30 words or fewer. Prefer a single sentence; use two only if both are short.
- Return only the JSON object. No markdown, no explanation.

Visual types — choose "type" per slide based on what the content actually is:
- "bullets" (default): conceptual, definitional, or qualitative content. Use this unless the content clearly fits one of the types below.
- "curve_plot": content describes a function, growth/decay pattern, or distribution over a continuous variable. "visual" shape:
  {{"x_label": "<axis label>", "y_label": "<axis label>", "x_min": <number>, "x_max": <number>, "series": [{{"label": "<series name>", "points": [{{"x": <number>, "y": <number>}}, ...]}}]}}
  1 to 3 series, each with 8 to 30 points ordered by ascending x. Supply real sampled (x, y) values — never a symbolic expression or code.
- "bar_chart": content compares named discrete quantities. "visual" shape:
  {{"y_label": "<axis label>", "bars": [{{"label": "<name>", "value": <number>}}, ...]}}
  2 to 6 bars.
- "diagram": content describes spatial, relational, or set structure between named entities (including plain coordinate points, using shape "point"). "visual" shape:
  {{"nodes": [{{"id": "<short id>", "label": "<display label>", "x": <0-100>, "y": <0-100>, "shape": "<circle, rect, or point>"}}, ...], "edges": [{{"from": "<node id>", "to": "<node id>", "label": "<optional edge label>"}}, ...]}}
  2 to 6 nodes, 0 to 5 edges. x and y are percentages of the canvas (0-100). Every edge's "from" and "to" must match a node "id".
- "formula": the slide centers on one named equation worth breaking into parts. "visual" shape:
  {{"latex": "<LaTeX with each annotated part wrapped in \\htmlId{{<id>}}{{<expression>}}>", "annotations": [{{"id": "<matching id>", "label": "<what this part means>"}}, ...]}}
  1 to 4 annotations. Every annotation "id" must appear as a \\htmlId{{...}} wrapper somewhere in "latex".

Across the whole deck, no more than half the slides should use a non-"bullets" type — visuals should earn their place on a slide, not be used for novelty.\
"""
```

Note on escaping: this is a plain (non-raw) triple-quoted Python string consumed by `.format(text=text)`. Every literal `{` / `}` in the JSON schema examples is doubled (`{{` / `}}`) to survive `.format()`, exactly like the existing template already does. `.format()` never touches backslashes — only Python's own string-literal parsing does — so the literal backslash before `htmlId` needs doubling only once (`\\htmlId` in source, two backslash characters) to produce a single literal backslash (`\htmlId`) in the runtime string, matching the `\htmlId{...}{...}` KaTeX syntax from the spec and Task 1's `f"\\htmlId{{{ann.id}}}"` check.

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && pytest tests/test_script_generator.py -v`
Expected: PASS (all tests, including the pre-existing `test_user_template_caps_narration_speaking_length`, which must still pass unchanged)

- [ ] **Step 5: Commit**

```bash
git add backend/script_generator.py backend/tests/test_script_generator.py
git commit -m "feat: document visual template schemas in the script generation prompt

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

### Task 5: Shared TypeScript types for visual slides

**Files:**
- Modify: `render/src/LearnFlowVideo.tsx:4-11` (the `SlideData` type)

**Interfaces:**
- Produces: `CurvePlotVisual`, `BarChartVisual`, `DiagramVisual`, `FormulaVisual` (TS types, field-for-field matching the pydantic models from Task 1), and `SlideData` as a discriminated union on `type`. Tasks 6-11 import these from `./LearnFlowVideo`.

- [ ] **Step 1: Replace the `SlideData` type**

In `render/src/LearnFlowVideo.tsx`, replace:

```tsx
export type SlideData = {
  index: number
  title: string
  narration: string
  bullets: string[]
  audio_static_path: string
  duration_seconds: number
}
```

with:

```tsx
export type CurvePoint = { x: number; y: number }
export type CurveSeries = { label: string; points: CurvePoint[] }
export type CurvePlotVisual = {
  x_label: string
  y_label: string
  x_min: number
  x_max: number
  series: CurveSeries[]
}

export type Bar = { label: string; value: number }
export type BarChartVisual = { y_label: string; bars: Bar[] }

export type DiagramNode = { id: string; label: string; x: number; y: number; shape: 'circle' | 'rect' | 'point' }
export type DiagramEdge = { from: string; to: string; label?: string }
export type DiagramVisual = { nodes: DiagramNode[]; edges: DiagramEdge[] }

export type FormulaAnnotation = { id: string; label: string }
export type FormulaVisual = { latex: string; annotations: FormulaAnnotation[] }

type SlideBase = {
  index: number
  title: string
  narration: string
  bullets: string[]
  audio_static_path: string
  duration_seconds: number
}

export type BulletsSlideData = SlideBase & { type: 'bullets' }
export type CurvePlotSlideData = SlideBase & { type: 'curve_plot'; visual: CurvePlotVisual }
export type BarChartSlideData = SlideBase & { type: 'bar_chart'; visual: BarChartVisual }
export type DiagramSlideData = SlideBase & { type: 'diagram'; visual: DiagramVisual }
export type FormulaSlideData = SlideBase & { type: 'formula'; visual: FormulaVisual }

export type SlideData =
  | BulletsSlideData
  | CurvePlotSlideData
  | BarChartSlideData
  | DiagramSlideData
  | FormulaSlideData
```

- [ ] **Step 2: Type-check**

Run: `cd render && npx tsc --noEmit`
Expected: One error, in `Root.tsx`, because the placeholder `defaultProps` slide object no longer matches `SlideData` (it's missing `type`). This is expected — Task 11 fixes it. Confirm the error is exactly this (a missing `type` property on the `defaultProps` slide literal) and no other file is affected.

- [ ] **Step 3: Commit**

```bash
git add render/src/LearnFlowVideo.tsx
git commit -m "feat: add discriminated union types for visual slide payloads

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

Note: this commit intentionally leaves the repo in a non-type-checking state (the known `Root.tsx` error from Step 2) — Task 11 resolves it. This mirrors the plan's dependency order: types must exist before every component that consumes them.

---

### Task 6: Visual error boundary

**Files:**
- Create: `render/src/visuals/VisualErrorBoundary.tsx`

**Interfaces:**
- Produces: `VisualErrorBoundary` (React component, props `{ fallback: ReactNode; children: ReactNode }`). Task 11 wraps each visual component with it.

- [ ] **Step 1: Implement**

```tsx
// render/src/visuals/VisualErrorBoundary.tsx
import { Component, ReactNode } from 'react'

type Props = {
  fallback: ReactNode
  children: ReactNode
}

type State = { hasError: boolean }

export class VisualErrorBoundary extends Component<Props, State> {
  state: State = { hasError: false }

  static getDerivedStateFromError(): State {
    return { hasError: true }
  }

  componentDidCatch(error: Error) {
    console.error('Visual component failed to render, falling back to bullets:', error)
  }

  render() {
    if (this.state.hasError) {
      return this.props.fallback
    }
    return this.props.children
  }
}
```

React error boundaries must be class components — there is no hook-based equivalent as of React 18, which is why this doesn't follow the functional-component style used elsewhere in `render/src`.

- [ ] **Step 2: Type-check**

Run: `cd render && npx tsc --noEmit`
Expected: Same single pre-existing `Root.tsx` error from Task 5, and no new errors from this file.

- [ ] **Step 3: Commit**

```bash
git add render/src/visuals/VisualErrorBoundary.tsx
git commit -m "feat: add error boundary for visual slide components

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

### Task 7: Curve plot component

**Files:**
- Create: `render/src/visuals/CurvePlot.tsx`

**Interfaces:**
- Consumes: `CurvePlotVisual` from `../LearnFlowVideo` (Task 5)
- Produces: `CurvePlot` (React component, props `{ visual: CurvePlotVisual }`). Task 11 imports this.

- [ ] **Step 1: Implement**

```tsx
// render/src/visuals/CurvePlot.tsx
import { interpolate, useCurrentFrame, useVideoConfig, spring } from 'remotion'
import { CurvePlotVisual } from '../LearnFlowVideo'

const COLORS = ['#7c3aed', '#22c55e', '#e0e0ff']
const PLOT_WIDTH = 1400
const PLOT_HEIGHT = 700
const MARGIN = 80
// Approximate upper bound on any series' on-screen path length, used only to
// drive the stroke-dasharray "draw in" reveal. It doesn't need to be exact —
// it only needs to exceed the real length so the dash offset fully hides the
// path at progress 0.
const APPROX_PATH_LENGTH = 4000

function toScreen(x: number, y: number, visual: CurvePlotVisual, yMin: number, yMax: number) {
  const px = MARGIN + ((x - visual.x_min) / (visual.x_max - visual.x_min)) * (PLOT_WIDTH - 2 * MARGIN)
  const py = MARGIN + (1 - (y - yMin) / (yMax - yMin)) * (PLOT_HEIGHT - 2 * MARGIN)
  return { px, py }
}

export function CurvePlot({ visual }: { visual: CurvePlotVisual }) {
  const frame = useCurrentFrame()
  const { fps } = useVideoConfig()

  const allY = visual.series.flatMap((s) => s.points.map((p) => p.y))
  const yMin = Math.min(...allY)
  const yMax = Math.max(...allY)

  const axisOpacity = spring({ frame, fps, config: { damping: 200 } })

  return (
    <svg width={PLOT_WIDTH} height={PLOT_HEIGHT} viewBox={`0 0 ${PLOT_WIDTH} ${PLOT_HEIGHT}`}>
      <line
        x1={MARGIN} y1={PLOT_HEIGHT - MARGIN} x2={PLOT_WIDTH - MARGIN} y2={PLOT_HEIGHT - MARGIN}
        stroke="#c0c0e0" strokeWidth={2} opacity={axisOpacity}
      />
      <line
        x1={MARGIN} y1={MARGIN} x2={MARGIN} y2={PLOT_HEIGHT - MARGIN}
        stroke="#c0c0e0" strokeWidth={2} opacity={axisOpacity}
      />
      <text x={PLOT_WIDTH / 2} y={PLOT_HEIGHT - 20} fill="#c0c0e0" fontSize={28} textAnchor="middle" opacity={axisOpacity}>
        {visual.x_label}
      </text>
      <text
        x={24} y={PLOT_HEIGHT / 2} fill="#c0c0e0" fontSize={28} textAnchor="middle" opacity={axisOpacity}
        transform={`rotate(-90, 24, ${PLOT_HEIGHT / 2})`}
      >
        {visual.y_label}
      </text>
      {visual.series.map((series, i) => {
        const pathD = series.points
          .map((p, j) => {
            const { px, py } = toScreen(p.x, p.y, visual, yMin, yMax)
            return `${j === 0 ? 'M' : 'L'} ${px} ${py}`
          })
          .join(' ')
        const drawProgress = interpolate(frame, [15 + i * 10, 60 + i * 10], [0, 1], {
          extrapolateLeft: 'clamp',
          extrapolateRight: 'clamp',
        })
        return (
          <path
            key={i}
            d={pathD}
            fill="none"
            stroke={COLORS[i % COLORS.length]}
            strokeWidth={5}
            strokeDasharray={APPROX_PATH_LENGTH}
            strokeDashoffset={APPROX_PATH_LENGTH * (1 - drawProgress)}
          />
        )
      })}
      {visual.series.map((series, i) => (
        <text key={i} x={PLOT_WIDTH - MARGIN - 220} y={MARGIN + 30 + i * 36} fill={COLORS[i % COLORS.length]} fontSize={28}>
          {series.label}
        </text>
      ))}
    </svg>
  )
}
```

- [ ] **Step 2: Type-check**

Run: `cd render && npx tsc --noEmit`
Expected: Same single pre-existing `Root.tsx` error from Task 5, no new errors.

- [ ] **Step 3: Commit**

```bash
git add render/src/visuals/CurvePlot.tsx
git commit -m "feat: add animated curve plot visual component

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

### Task 8: Bar chart component

**Files:**
- Create: `render/src/visuals/BarChart.tsx`

**Interfaces:**
- Consumes: `BarChartVisual` from `../LearnFlowVideo` (Task 5)
- Produces: `BarChart` (React component, props `{ visual: BarChartVisual }`). Task 11 imports this.

- [ ] **Step 1: Implement**

```tsx
// render/src/visuals/BarChart.tsx
import { spring, useCurrentFrame, useVideoConfig } from 'remotion'
import { BarChartVisual } from '../LearnFlowVideo'

const CHART_WIDTH = 1400
const CHART_HEIGHT = 700
const MARGIN = 80
const BAR_COLOR = '#7c3aed'

export function BarChart({ visual }: { visual: BarChartVisual }) {
  const frame = useCurrentFrame()
  const { fps } = useVideoConfig()

  const maxValue = Math.max(...visual.bars.map((b) => b.value))
  const plotHeight = CHART_HEIGHT - 2 * MARGIN
  const plotWidth = CHART_WIDTH - 2 * MARGIN
  const gap = plotWidth / visual.bars.length
  const barWidth = gap / 1.6

  return (
    <svg width={CHART_WIDTH} height={CHART_HEIGHT} viewBox={`0 0 ${CHART_WIDTH} ${CHART_HEIGHT}`}>
      <line
        x1={MARGIN} y1={CHART_HEIGHT - MARGIN} x2={CHART_WIDTH - MARGIN} y2={CHART_HEIGHT - MARGIN}
        stroke="#c0c0e0" strokeWidth={2}
      />
      <text x={CHART_WIDTH / 2} y={30} fill="#c0c0e0" fontSize={28} textAnchor="middle">
        {visual.y_label}
      </text>
      {visual.bars.map((bar, i) => {
        const growth = spring({ frame: frame - i * 6, fps, config: { damping: 15, mass: 0.6 } })
        const barHeight = (bar.value / maxValue) * plotHeight * Math.max(growth, 0)
        const x = MARGIN + i * gap + (gap - barWidth) / 2
        const y = CHART_HEIGHT - MARGIN - barHeight
        return (
          <g key={i}>
            <rect x={x} y={y} width={barWidth} height={barHeight} fill={BAR_COLOR} rx={6} />
            <text x={x + barWidth / 2} y={CHART_HEIGHT - MARGIN + 36} fill="#c0c0e0" fontSize={24} textAnchor="middle">
              {bar.label}
            </text>
            <text x={x + barWidth / 2} y={y - 14} fill="#e0e0ff" fontSize={24} textAnchor="middle">
              {bar.value}
            </text>
          </g>
        )
      })}
    </svg>
  )
}
```

- [ ] **Step 2: Type-check**

Run: `cd render && npx tsc --noEmit`
Expected: Same single pre-existing `Root.tsx` error from Task 5, no new errors.

- [ ] **Step 3: Commit**

```bash
git add render/src/visuals/BarChart.tsx
git commit -m "feat: add animated bar chart visual component

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

### Task 9: Diagram component

**Files:**
- Create: `render/src/visuals/Diagram.tsx`

**Interfaces:**
- Consumes: `DiagramVisual` from `../LearnFlowVideo` (Task 5)
- Produces: `Diagram` (React component, props `{ visual: DiagramVisual }`). Task 11 imports this.

- [ ] **Step 1: Implement**

```tsx
// render/src/visuals/Diagram.tsx
import { spring, useCurrentFrame, useVideoConfig } from 'remotion'
import { DiagramVisual, DiagramNode } from '../LearnFlowVideo'

const CANVAS_SIZE = 1200

function nodePos(n: { x: number; y: number }) {
  return { px: (n.x / 100) * CANVAS_SIZE, py: (n.y / 100) * CANVAS_SIZE }
}

export function Diagram({ visual }: { visual: DiagramVisual }) {
  const frame = useCurrentFrame()
  const { fps } = useVideoConfig()
  const nodeById: Record<string, DiagramNode> = Object.fromEntries(visual.nodes.map((n) => [n.id, n]))

  return (
    <svg width={CANVAS_SIZE} height={CANVAS_SIZE} viewBox={`0 0 ${CANVAS_SIZE} ${CANVAS_SIZE}`}>
      {visual.edges.map((edge, i) => {
        const from = nodeById[edge.from]
        const to = nodeById[edge.to]
        const a = nodePos(from)
        const b = nodePos(to)
        const drawProgress = spring({ frame: frame - 20 - i * 8, fps, config: { damping: 200 } })
        const midX = a.px + (b.px - a.px) * drawProgress
        const midY = a.py + (b.py - a.py) * drawProgress
        return (
          <g key={i}>
            <line x1={a.px} y1={a.py} x2={midX} y2={midY} stroke="#7c3aed" strokeWidth={4} />
            {edge.label && drawProgress > 0.9 && (
              <text x={(a.px + b.px) / 2} y={(a.py + b.py) / 2 - 12} fill="#c0c0e0" fontSize={22} textAnchor="middle">
                {edge.label}
              </text>
            )}
          </g>
        )
      })}
      {visual.nodes.map((node, i) => {
        const { px, py } = nodePos(node)
        const scale = spring({ frame: frame - i * 6, fps, config: { damping: 12, mass: 0.5 } })
        if (node.shape === 'point') {
          return (
            <g key={node.id} transform={`translate(${px}, ${py}) scale(${scale})`}>
              <circle r={8} fill="#22c55e" />
              <text x={16} y={6} fill="#c0c0e0" fontSize={22}>{node.label}</text>
            </g>
          )
        }
        const shapeEl =
          node.shape === 'circle' ? (
            <circle r={70} fill="#16213e" stroke="#7c3aed" strokeWidth={4} />
          ) : (
            <rect x={-90} y={-50} width={180} height={100} rx={12} fill="#16213e" stroke="#7c3aed" strokeWidth={4} />
          )
        return (
          <g key={node.id} transform={`translate(${px}, ${py}) scale(${scale})`}>
            {shapeEl}
            <text fill="#e0e0ff" fontSize={26} textAnchor="middle" dominantBaseline="middle">
              {node.label}
            </text>
          </g>
        )
      })}
    </svg>
  )
}
```

- [ ] **Step 2: Type-check**

Run: `cd render && npx tsc --noEmit`
Expected: Same single pre-existing `Root.tsx` error from Task 5, no new errors.

- [ ] **Step 3: Commit**

```bash
git add render/src/visuals/Diagram.tsx
git commit -m "feat: add animated diagram visual component

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

### Task 10: Formula highlight component

**Files:**
- Create: `render/src/visuals/FormulaHighlight.tsx`
- Modify: `render/package.json` (add `katex` + `@types/katex`)

**Interfaces:**
- Consumes: `FormulaVisual` from `../LearnFlowVideo` (Task 5)
- Produces: `FormulaHighlight` (React component, props `{ visual: FormulaVisual }`). Task 11 imports this.

- [ ] **Step 1: Add the KaTeX dependency**

```bash
cd render && npm install katex@^0.16.11 && npm install --save-dev @types/katex@^0.16.7
```

- [ ] **Step 2: Implement**

```tsx
// render/src/visuals/FormulaHighlight.tsx
import { useLayoutEffect, useMemo, useRef, useState } from 'react'
import { spring, useCurrentFrame, useVideoConfig } from 'remotion'
import katex from 'katex'
import 'katex/dist/katex.min.css'
import { FormulaVisual } from '../LearnFlowVideo'

type Position = { x: number; y: number }

export function FormulaHighlight({ visual }: { visual: FormulaVisual }) {
  const frame = useCurrentFrame()
  const { fps } = useVideoConfig()
  const containerRef = useRef<HTMLDivElement>(null)
  const [positions, setPositions] = useState<Record<string, Position>>({})

  const html = useMemo(
    () =>
      katex.renderToString(visual.latex, {
        throwOnError: false,
        trust: (context) => context.command === '\\htmlId' || context.command === '\\htmlClass',
      }),
    [visual.latex]
  )

  useLayoutEffect(() => {
    const container = containerRef.current
    if (!container) return
    const containerBox = container.getBoundingClientRect()
    const next: Record<string, Position> = {}
    for (const ann of visual.annotations) {
      const el = container.querySelector(`#${CSS.escape(ann.id)}`)
      if (!el) continue
      const box = el.getBoundingClientRect()
      next[ann.id] = {
        x: box.left + box.width / 2 - containerBox.left,
        y: box.top + box.height - containerBox.top,
      }
    }
    setPositions(next)
  }, [html, visual.annotations])

  const equationScale = spring({ frame, fps, config: { damping: 14, mass: 0.6 } })

  return (
    <div
      style={{
        width: '100%', height: '100%', position: 'relative',
        display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
      }}
    >
      <div
        ref={containerRef}
        style={{ fontSize: 56, color: '#e0e0ff', transform: `scale(${equationScale})`, position: 'relative' }}
        dangerouslySetInnerHTML={{ __html: html }}
      />
      <svg style={{ position: 'absolute', top: 0, left: 0, width: '100%', height: '100%', pointerEvents: 'none' }}>
        {visual.annotations.map((ann, i) => {
          const pos = positions[ann.id]
          if (!pos) return null
          const reveal = spring({ frame: frame - 30 - i * 15, fps, config: { damping: 200 } })
          if (reveal <= 0) return null
          const labelY = pos.y + 60 + i * 44
          return (
            <g key={ann.id} opacity={reveal}>
              <line x1={pos.x} y1={pos.y} x2={pos.x} y2={labelY - 10} stroke="#7c3aed" strokeWidth={3} />
              <circle cx={pos.x} cy={pos.y} r={5} fill="#7c3aed" />
              <text x={pos.x} y={labelY + 10} fill="#c0c0e0" fontSize={24} textAnchor="middle">
                {ann.label}
              </text>
            </g>
          )
        })}
      </svg>
    </div>
  )
}
```

`\htmlId`/`\htmlClass` are otherwise-untrusted KaTeX commands, so `trust` is scoped to a predicate that allows exactly those two — never `trust: true`, which would also enable `\href` and other commands that shouldn't be reachable from PDF-derived content (per the Global Constraints). Leader-line positions are measured via `useLayoutEffect` (runs synchronously after DOM mutation, before paint) rather than computed analytically, since KaTeX's own internal glyph layout isn't something this component should reimplement.

- [ ] **Step 3: Type-check**

Run: `cd render && npx tsc --noEmit`
Expected: Same single pre-existing `Root.tsx` error from Task 5, no new errors.

- [ ] **Step 4: Commit**

```bash
git add render/package.json render/package-lock.json render/src/visuals/FormulaHighlight.tsx
git commit -m "feat: add animated formula highlight visual component

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

### Task 11: Slide dispatcher and Root defaults

**Files:**
- Modify: `render/src/Slide.tsx` (full rewrite)
- Modify: `render/src/Root.tsx:10-22` (`defaultProps`)

**Interfaces:**
- Consumes: `SlideData` (Task 5), `VisualErrorBoundary` (Task 6), `CurvePlot` (Task 7), `BarChart` (Task 8), `Diagram` (Task 9), `FormulaHighlight` (Task 10)

- [ ] **Step 1: Rewrite `Slide.tsx`**

```tsx
// render/src/Slide.tsx
import { ReactNode } from 'react'
import { SlideData } from './LearnFlowVideo'
import { CurvePlot } from './visuals/CurvePlot'
import { BarChart } from './visuals/BarChart'
import { Diagram } from './visuals/Diagram'
import { FormulaHighlight } from './visuals/FormulaHighlight'
import { VisualErrorBoundary } from './visuals/VisualErrorBoundary'

function BulletsLayout({ slide }: { slide: SlideData }) {
  return (
    <div
      style={{
        background: '#1a1a2e', width: '100%', height: '100%',
        display: 'flex', flexDirection: 'column', padding: '80px', boxSizing: 'border-box',
      }}
    >
      <h1 style={{ color: '#e0e0ff', fontFamily: 'sans-serif', fontSize: '64px', margin: '0 0 48px 0' }}>
        {slide.title}
      </h1>
      <ul style={{ color: '#c0c0e0', fontFamily: 'sans-serif', fontSize: '40px', lineHeight: '1.6', paddingLeft: '48px', margin: 0 }}>
        {slide.bullets.map((b, i) => (
          <li key={i}>{b}</li>
        ))}
      </ul>
    </div>
  )
}

function visualFor(slide: SlideData): ReactNode {
  switch (slide.type) {
    case 'curve_plot':
      return <CurvePlot visual={slide.visual} />
    case 'bar_chart':
      return <BarChart visual={slide.visual} />
    case 'diagram':
      return <Diagram visual={slide.visual} />
    case 'formula':
      return <FormulaHighlight visual={slide.visual} />
    case 'bullets':
      return null
  }
}

export function Slide({ slide }: { slide: SlideData }) {
  const bulletsFallback = <BulletsLayout slide={slide} />
  const visualEl = visualFor(slide)

  if (!visualEl) {
    return bulletsFallback
  }

  return (
    <div
      style={{
        background: '#1a1a2e', width: '100%', height: '100%',
        display: 'flex', flexDirection: 'column', padding: '60px', boxSizing: 'border-box',
      }}
    >
      <h1 style={{ color: '#e0e0ff', fontFamily: 'sans-serif', fontSize: '48px', margin: '0 0 24px 0' }}>
        {slide.title}
      </h1>
      <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <VisualErrorBoundary fallback={bulletsFallback}>{visualEl}</VisualErrorBoundary>
      </div>
    </div>
  )
}
```

- [ ] **Step 2: Fix `Root.tsx`'s placeholder slide**

In `render/src/Root.tsx`, the `defaultProps` slide literal currently reads:

```tsx
  slides: [
    {
      index: 0,
      title: 'Slide',
      narration: '',
      bullets: [''],
      audio_static_path: '',
      duration_seconds: MIN_SLIDE_SECONDS,
    },
  ],
```

Add `type: 'bullets'`:

```tsx
  slides: [
    {
      index: 0,
      title: 'Slide',
      narration: '',
      bullets: [''],
      audio_static_path: '',
      duration_seconds: MIN_SLIDE_SECONDS,
      type: 'bullets',
    },
  ],
```

- [ ] **Step 3: Type-check — this must now be fully clean**

Run: `cd render && npx tsc --noEmit`
Expected: PASS with zero errors (the `Root.tsx` error carried since Task 5 is now resolved).

- [ ] **Step 4: Commit**

```bash
git add render/src/Slide.tsx render/src/Root.tsx
git commit -m "feat: dispatch slide rendering to the matching visual template

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

### Task 12: End-to-end verification

**Files:** none (verification only — no new files)

This task is deliberately not automated: it's the "does this actually work, rendered, on screen" gate, matching how every prior render-pipeline feature in this project (TTS sync, the WSL2 render path, the Docker deployment) was ultimately verified by watching a real render, not by trusting code on paper. It doesn't rely on Claude choosing to use all four visual types in one real generation (it may not, since the prompt explicitly caps visual usage) — it uses a hand-crafted props file that exercises every type deterministically.

- [ ] **Step 1: Write a hand-crafted props file covering all five slide types**

Create `render/out/manual-test-props.json` (this directory is already gitignored — do not commit this file):

```json
{
  "title": "Visual Template Smoke Test",
  "slides": [
    {
      "index": 0,
      "title": "Bullets (baseline)",
      "narration": "",
      "bullets": ["First point", "Second point", "Third point"],
      "audio_static_path": "",
      "duration_seconds": 4,
      "type": "bullets"
    },
    {
      "index": 1,
      "title": "Curve Plot",
      "narration": "",
      "bullets": ["f(x) = x squared"],
      "audio_static_path": "",
      "duration_seconds": 5,
      "type": "curve_plot",
      "visual": {
        "x_label": "x", "y_label": "f(x)", "x_min": -5, "x_max": 5,
        "series": [{"label": "f(x) = x^2", "points": [{"x": -5, "y": 25}, {"x": -4, "y": 16}, {"x": -3, "y": 9}, {"x": -2, "y": 4}, {"x": -1, "y": 1}, {"x": 0, "y": 0}, {"x": 1, "y": 1}, {"x": 2, "y": 4}, {"x": 3, "y": 9}, {"x": 4, "y": 16}, {"x": 5, "y": 25}]}]
      }
    },
    {
      "index": 2,
      "title": "Bar Chart",
      "narration": "",
      "bullets": ["Threat X vs Threat Y"],
      "audio_static_path": "",
      "duration_seconds": 5,
      "type": "bar_chart",
      "visual": {"y_label": "Expected Damage ($)", "bars": [{"label": "Threat X", "value": 800}, {"label": "Threat Y", "value": 2000}]}
    },
    {
      "index": 3,
      "title": "Diagram",
      "narration": "",
      "bullets": ["Sample space contains event A"],
      "audio_static_path": "",
      "duration_seconds": 5,
      "type": "diagram",
      "visual": {
        "nodes": [{"id": "A", "label": "Sample Space Ω", "x": 50, "y": 30, "shape": "circle"}, {"id": "B", "label": "Event A", "x": 30, "y": 65, "shape": "rect"}],
        "edges": [{"from": "A", "to": "B", "label": "contains"}]
      }
    },
    {
      "index": 4,
      "title": "Formula Highlight",
      "narration": "",
      "bullets": ["Expected value formula"],
      "audio_static_path": "",
      "duration_seconds": 5,
      "type": "formula",
      "visual": {
        "latex": "\\htmlId{term-mean}{E[X]} = \\sum_{i} \\htmlId{term-outcome}{x_i} \\htmlId{term-prob}{P(x_i)}",
        "annotations": [{"id": "term-mean", "label": "Expected value"}, {"id": "term-outcome", "label": "Each outcome"}, {"id": "term-prob", "label": "Its probability"}]
      }
    }
  ]
}
```

Note: `audio_static_path` is left empty and `duration_seconds` is small but nonzero — this file is for visually inspecting the five slide layouts and animations in Remotion Studio, not for producing a shippable video, so a missing/silent audio track is fine.

- [ ] **Step 2: Open Remotion Studio and load the props**

```bash
cd render && npm run studio
```

In the Studio UI: select the `LearnFlowVideo` composition, open the input props panel, and paste in the contents of `render/out/manual-test-props.json`.

- [ ] **Step 3: Visually verify each slide**

Scrub through the timeline (5 slides, ~4-5s each) and confirm for each:
- **Slide 0 (bullets):** unchanged from before this feature — three bullets, no visual.
- **Slide 1 (curve plot):** a parabola draws in left-to-right, axes labeled "x" / "f(x)", violet line.
- **Slide 2 (bar chart):** two bars grow upward from the baseline, staggered, labeled "Threat X" / "Threat Y" with their values shown above each bar.
- **Slide 3 (diagram):** a circle labeled "Sample Space Ω" and a rectangle labeled "Event A" scale in, then a line labeled "contains" draws between them.
- **Slide 4 (formula):** the equation `E[X] = Σᵢ xᵢP(xᵢ)` renders as real typeset math (not raw LaTeX text), scales in, then three annotation labels with leader-lines pointing at `E[X]`, `xᵢ`, and `P(xᵢ)` appear staggered below/around the equation.

If any slide fails to render or throws, `VisualErrorBoundary` should make it fall back to that slide's plain bullets layout instead of crashing Studio's preview entirely — confirm this by temporarily breaking one field (e.g., change slide 2's `bars` to a single entry) and reloading; that slide should degrade to bullets while the rest of the deck keeps working. Revert the temporary breakage afterward.

- [ ] **Step 4: Confirm the full backend pipeline still produces valid output**

Run the existing full backend test suite to confirm nothing in the surrounding pipeline (TTS, render route, quiz, eval) regressed:

```bash
cd backend && pytest -v
```

Expected: all tests pass, including every test added in Tasks 1-4.

- [ ] **Step 5: Delete the manual test props file**

```bash
rm render/out/manual-test-props.json
```

(Already gitignored, but this keeps the working tree clean since it was never meant to be committed.)

No commit for this task — it verifies work already committed in Tasks 1-11.

---

## Self-Review Notes

- **Spec coverage:** §3 (data shapes) → Task 1 models; §4 (schema) → Task 5 TS types + Task 1/2 Python; §5 (prompt) → Task 4; §6 (validation/fallback) → Tasks 2-3 (Python primary) + Task 6 (TS backstop); §7 (Remotion components/theme) → Tasks 7-11; §8 (out of scope) — nothing in this plan exceeds it (no 5th template, no animation-timing narration, no symbolic math evaluation).
- **Type consistency check:** `_VISUAL_MODELS` (Task 1) is consumed by `_sanitize_slide_types` (Task 2) with matching signature `dict[str, type[BaseModel]]`. `SlideData`'s discriminated union (Task 5) field names (`x_label`, `y_label`, `bars`, `nodes`, `edges`, `from`/`to`, `latex`, `annotations`) match the pydantic models' field names (Task 1) and the prompt's JSON schema (Task 4) exactly, including the Python-side `from_`/alias `"from"` split being purely a Python-reserved-word workaround with no TS-side equivalent needed.
