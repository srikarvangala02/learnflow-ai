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


def test_diagram_rejects_6_edges():
    with pytest.raises(ValidationError):
        DiagramVisual.model_validate({
            "nodes": [
                {"id": "A", "label": "A", "x": 50, "y": 30, "shape": "circle"},
                {"id": "B", "label": "B", "x": 30, "y": 60, "shape": "circle"},
            ],
            "edges": [
                {"from": "A", "to": "B"},
                {"from": "B", "to": "A"},
                {"from": "A", "to": "B", "label": "second"},
                {"from": "B", "to": "A", "label": "second"},
                {"from": "A", "to": "B", "label": "third"},
                {"from": "B", "to": "A", "label": "third"},
            ],
        })


def test_formula_rejects_0_annotations():
    with pytest.raises(ValidationError):
        FormulaVisual.model_validate({
            "latex": "\\htmlId{a}{E[X]}",
            "annotations": [],
        })


def test_formula_rejects_5_annotations():
    with pytest.raises(ValidationError):
        FormulaVisual.model_validate({
            "latex": "\\htmlId{a}{A} \\htmlId{b}{B} \\htmlId{c}{C} \\htmlId{d}{D} \\htmlId{e}{E}",
            "annotations": [
                {"id": "a", "label": "First"},
                {"id": "b", "label": "Second"},
                {"id": "c", "label": "Third"},
                {"id": "d", "label": "Fourth"},
                {"id": "e", "label": "Fifth"},
            ],
        })


def test_visual_models_registry_has_all_four_types():
    assert set(_VISUAL_MODELS.keys()) == {"curve_plot", "bar_chart", "diagram", "formula"}


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
