import os
import io
import yaml
from typing import List, Tuple
from docx import Document as DocxDocument
from pdfminer.high_level import extract_text
from charset_normalizer import from_bytes

def ensure_dirs(paths: List[str]):
    for p in paths:
        os.makedirs(p, exist_ok=True)

def read_file_bytes(path: str) -> bytes:
    with open(path, "rb") as f:
        return f.read()

def detect_encoding(data: bytes) -> str:
    result = from_bytes(data).best()
    return result.encoding if result else "utf-8"

def read_text_from_docx(path: str) -> str:
    doc = DocxDocument(path)
    lines = []
    for p in doc.paragraphs:
        lines.append(p.text)
    text = "\n".join(lines)
    # Нормализация переносов/колонтитулов — можно расширять
    return normalize_whitespace(text)

def normalize_whitespace(text: str) -> str:
    import re
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()

def read_text_from_pdf(path: str, return_spans: bool = False):
    # Быстрый путь: получить весь текст и позиции страниц
    # extract_text даёт склейку текстов; для приблизительных страниц
    text = extract_text(path)
    text = normalize_whitespace(text)
    if not return_spans:
        return text
    # Грубая оценка page_spans: извлекаем ещё раз постранично
    page_spans = []
    offset = 0
    try:
        from pdfminer.high_level import extract_pages
        from pdfminer.layout import LTTextContainer
        pages = list(extract_pages(path))
        for pidx, page in enumerate(pages):
            start = offset
            buf = []
            for element in page:
                if isinstance(element, LTTextContainer):
                    buf.append(element.get_text())
            page_text = normalize_whitespace("\n".join(buf))
            offset += len(page_text)
            page_spans.append((pidx, start, offset))
    except Exception:
        pass
    return text, page_spans

def read_yaml(path: str):
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)
