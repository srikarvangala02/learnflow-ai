import json
import os
from pathlib import Path

import anthropic
import pdfplumber

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
      "answer": "<A, B, C, or D>"
    }}
  ]
}}

Rules:
- Generate between 3 and 5 questions.
- Each question must have exactly 4 options labelled A through D.
- Only one option is correct; set "answer" to its letter.
- Questions must test understanding, not surface recall of exact wording.
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
      "narration": "<1-3 sentence paragraph suitable for text-to-speech>",
      "bullets": ["<key point>", ...]
    }}
  ]
}}

Rules:
- Generate between 5 and 8 slides.
- Each slide must have 2 to 4 bullets.
- Narration must be complete sentences, not bullet points.
- Return only the JSON object. No markdown, no explanation.\
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
