from __future__ import annotations

import io
import re
from typing import List

import pdfplumber


def extract_text_from_pdf_bytes(file_bytes: bytes) -> str:
    text_parts: List[str] = []
    with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text() or ""
            if page_text:
                text_parts.append(page_text)
    return "\n\n".join(part.strip() for part in text_parts if part.strip())


def clean_extracted_text(text: str) -> str:
    raw = str(text or "")
    raw = raw.replace("\x00", " ")
    raw = raw.replace("\r\n", "\n").replace("\r", "\n")
    raw = re.sub(r"[ \t]+", " ", raw)
    raw = re.sub(r"\n{3,}", "\n\n", raw)
    lines = [line.rstrip() for line in raw.split("\n")]
    return "\n".join(lines).strip()
