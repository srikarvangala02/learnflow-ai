import json
import os
from pathlib import Path

import anthropic
import pdfplumber

_SYSTEM_PROMPT = (
    "You are an expert educator creating a narrated slide deck from source material. "
    "Your output must be valid JSON and nothing else — no markdown fences, no commentary."
)

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
