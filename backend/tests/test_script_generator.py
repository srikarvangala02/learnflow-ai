import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from script_generator import extract_text, generate_script, _USER_TEMPLATE


def _make_mock_pdf(pages):
    """pages: list of str|None — what each page's extract_text() returns."""
    mock_pages = []
    for text in pages:
        p = MagicMock()
        p.extract_text.return_value = text
        mock_pages.append(p)

    mock_pdf = MagicMock()
    mock_pdf.__enter__ = MagicMock(return_value=mock_pdf)
    mock_pdf.__exit__ = MagicMock(return_value=False)
    mock_pdf.pages = mock_pages
    return mock_pdf


def test_extract_text_joins_pages_with_double_newline(tmp_path):
    pdf_path = tmp_path / "test.pdf"
    pdf_path.write_bytes(b"placeholder")

    with patch("script_generator.pdfplumber.open", return_value=_make_mock_pdf(["First page", "Second page"])):
        result = extract_text(pdf_path)

    assert result == "First page\n\nSecond page"


def test_extract_text_treats_none_page_as_empty(tmp_path):
    pdf_path = tmp_path / "test.pdf"
    pdf_path.write_bytes(b"placeholder")

    with patch("script_generator.pdfplumber.open", return_value=_make_mock_pdf([None])):
        result = extract_text(pdf_path)

    assert result == ""


def test_generate_script_returns_dict_with_file_id(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

    script_body = {
        "title": "Test Document",
        "slides": [
            {
                "index": 0,
                "title": "Introduction",
                "narration": "This is the narration.",
                "bullets": ["Point A", "Point B"],
            }
        ],
    }
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text=json.dumps(script_body))]

    with patch("script_generator.anthropic.Anthropic") as mock_cls:
        mock_cls.return_value.messages.create.return_value = mock_response
        result = generate_script("file-abc", "some source text")

    assert result["file_id"] == "file-abc"
    assert result["title"] == "Test Document"
    assert len(result["slides"]) == 1
    assert mock_cls.return_value.messages.create.call_count == 1


def test_generate_script_raises_value_error_when_no_api_key(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    with pytest.raises(ValueError, match="ANTHROPIC_API_KEY"):
        generate_script("file-abc", "some text")


def test_generate_script_retries_once_on_invalid_json(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

    valid_script = {
        "title": "Retry Test",
        "slides": [
            {
                "index": 0,
                "title": "S1",
                "narration": "Narration sentence.",
                "bullets": ["B1", "B2"],
            }
        ],
    }
    bad_response = MagicMock()
    bad_response.content = [MagicMock(text="not valid json {{{")]
    good_response = MagicMock()
    good_response.content = [MagicMock(text=json.dumps(valid_script))]

    with patch("script_generator.anthropic.Anthropic") as mock_cls:
        mock_cls.return_value.messages.create.side_effect = [bad_response, good_response]
        result = generate_script("file-abc", "some text")

    assert result["title"] == "Retry Test"
    assert mock_cls.return_value.messages.create.call_count == 2


def test_generate_script_raises_on_persistent_invalid_json(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

    bad_response = MagicMock()
    bad_response.content = [MagicMock(text="still not json")]

    with patch("script_generator.anthropic.Anthropic") as mock_cls:
        mock_cls.return_value.messages.create.return_value = bad_response
        with pytest.raises(json.JSONDecodeError):
            generate_script("file-abc", "some text")

    assert mock_cls.return_value.messages.create.call_count == 2


def test_user_template_caps_narration_speaking_length():
    assert "12 seconds" in _USER_TEMPLATE
