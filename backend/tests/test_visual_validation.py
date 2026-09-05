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
