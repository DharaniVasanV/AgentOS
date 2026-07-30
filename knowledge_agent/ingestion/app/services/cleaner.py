"""
app/services/cleaner.py

STEP 2: Plain Text Extractor & Cleaner.
Removes HTML, Markdown, duplicate spaces, formatting noise, and invalid unicode while preserving semantic meaning & paragraphs.
"""

import re
import html


def clean_text(raw_text: str) -> str:
    if not raw_text:
        return ""

    # 1. Unescape HTML entities
    text = html.unescape(raw_text)

    # 2. Remove HTML tags
    text = re.sub(r"<[^>]+>", " ", text)

    # 3. Remove markdown fences / bold / italic markers while preserving inner text
    text = re.sub(r"```[\s\S]*?```", " ", text)
    text = re.sub(r"`([^`]+)`", r"\1", text)
    text = re.sub(r"\*\*([^*]+)\*\*", r"\1", text)
    text = re.sub(r"\*([^*]+)\*", r"\1", text)
    text = re.sub(r"__([^_]+)__", r"\1", text)
    text = re.sub(r"_([^_]+)_", r"\1", text)

    # 4. Remove invalid unicode / non-printable control characters except line breaks
    text = re.sub(r"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]", "", text)

    # 5. Collapse multiple spaces and horizontal whitespace, but preserve single newlines
    lines = [re.sub(r"[ \t]+", " ", line).strip() for line in text.splitlines()]
    
    # 6. Filter out empty noise lines while keeping double newlines for paragraph breaks
    cleaned_paragraphs = []
    current_para = []
    for line in lines:
        if line:
            current_para.append(line)
        else:
            if current_para:
                cleaned_paragraphs.append(" ".join(current_para))
                current_para = []
    if current_para:
        cleaned_paragraphs.append(" ".join(current_para))

    return "\n\n".join(cleaned_paragraphs)
