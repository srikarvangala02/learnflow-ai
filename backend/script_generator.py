import json
import logging
import os
from pathlib import Path
from typing import Literal

import anthropic
import pdfplumber
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

    @model_validator(mode="after")
    def _check_x_domain(self) -> "CurvePlotVisual":
        if not (self.x_max > self.x_min):
            raise ValueError(f"x_max ({self.x_max}) must be greater than x_min ({self.x_min})")
        return self


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
            validated = model.model_validate(slide.get("visual") or {})
            slide = {**slide, "visual": validated.model_dump(by_alias=True)}
            sanitized.append(slide)
        except ValidationError as exc:
            logger.warning("Slide %s visual failed validation (%s); falling back to bullets", slide.get("index"), exc)
            fallback = {k: v for k, v in slide.items() if k != "visual"}
            fallback["type"] = "bullets"
            sanitized.append(fallback)

    return sanitized


_SYSTEM_PROMPT = (
    "You are an expert educator creating a narrated slide deck from source material. "
    "Your output must be valid JSON and nothing else — no markdown fences, no commentary."
)

_QUIZ_SYSTEM_PROMPT = (
    "You are an expert educator writing multiple-choice quiz questions to test comprehension. "
    "Your output must be valid JSON and nothing else — no markdown fences, no commentary."
)

_QUIZ_USER_TEMPLATE = """\
Source material:
{text}

Produce a JSON object with this exact schema:
{{
  "questions": [
    {{
      "question": "<question text>",
      "options": ["A. <option>", "B. <option>", "C. <option>", "D. <option>"],
      "answer": "<A, B, C, or D>",
      "topic": "<2-4 word concept label, title-case, no verbs, e.g. 'Bernoulli Expectation'>"
    }}
  ]
}}

Rules:
- Choose a question count between 3 and 8 based on content density: 3–4 for short or narrow source material, 5–6 for medium, 7–8 for long or dense material with many distinct testable concepts. Do not pad thin material with trivial questions to reach a higher count.
- topic must name the single concept the question tests — 2 to 4 words, title-case, no verbs.
- Each question must have exactly 4 options labelled A through D.
- Only one option is correct; set "answer" to its letter.
- Questions MUST require applying or reasoning about concepts — not recognising a definition or finding a sentence from the text. A student who memorised the slides word-for-word but does not understand the material should get these wrong.
- Each question should probe a different concept so the set gives broad coverage of the material.
- Wrong options must be plausible — a student who partially understands the topic should find them credible. Never use obviously absurd distractors.
- Prefer questions that ask "why", "what would happen if", "which scenario illustrates", or "how does X relate to Y" over "what is the definition of X".
- Return only the JSON object. No markdown, no explanation.\
"""

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


def extract_text(pdf_path: Path) -> str:
    with pdfplumber.open(pdf_path) as pdf:
        pages = [page.extract_text() or "" for page in pdf.pages]
    return "\n\n".join(pages)


def generate_script(file_id: str, text: str) -> dict:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY environment variable is not set")

    client = anthropic.Anthropic(api_key=api_key)

    def _call(messages: list) -> str:
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=4096,
            system=_SYSTEM_PROMPT,
            messages=messages,
        )
        return response.content[0].text.strip()

    user_msg = {"role": "user", "content": _USER_TEMPLATE.format(text=text)}
    raw = _call([user_msg])

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


def generate_quiz(script: dict) -> dict:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY environment variable is not set")

    client = anthropic.Anthropic(api_key=api_key)
    text = "\n\n".join(slide["narration"] for slide in script.get("slides", []))

    def _call(messages: list) -> str:
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=2048,
            system=_QUIZ_SYSTEM_PROMPT,
            messages=messages,
        )
        return response.content[0].text.strip()

    user_msg = {"role": "user", "content": _QUIZ_USER_TEMPLATE.format(text=text)}
    raw = _call([user_msg])

    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        raw2 = _call([
            user_msg,
            {"role": "assistant", "content": raw},
            {"role": "user", "content": "That was not valid JSON. Return only the JSON object, nothing else."},
        ])
        return json.loads(raw2)
