import os
import re
from typing import List, Dict, Any
from docx import Document as DocxDocument
from pdfminer.high_level import extract_pages
from pdfminer.layout import LTTextContainer
from app.models.schemas import Scene
from app.utils.io import read_text_from_pdf, read_text_from_docx
from app.utils.checksum import text_checksum

SCENE_SPLIT_REGEX = re.compile(r"(^|\n)(?:СЦЕНА\s+\d+|INT\.|EXT\.|ИНТ\.|НАТ\.|EXT\/INT\.|INT\/EXT\.)", re.IGNORECASE)

def load_document(path: str) -> Dict[str, Any]:
    ext = os.path.splitext(path)[1].lower()
    if ext == ".docx":
        return {"type": "docx", "path": path, "text": read_text_from_docx(path)}
    elif ext == ".pdf":
        return {"type": "pdf", "path": path, "pages": list(extract_pages(path))}
    else:
        raise ValueError("Unsupported format")

def segment_scenes(doc: Dict[str, Any]) -> List[Scene]:
    scenes: List[Scene] = []
    if doc["type"] == "docx":
        text = doc["text"]
        blocks = smart_scene_blocks(text)
        offset = 0
        for idx, block in enumerate(blocks):
            start = text.find(block, offset)
            end = start + len(block)
            offset = end
            scene_id = f"S{idx+1}"
            dialogues = extract_dialogues(block)
            scenes.append(Scene(
                id=scene_id, index=idx, text=block.strip(),
                offset_start=start, offset_end=end,
                dialogues=dialogues
            ))
    else:  # pdf
        text, page_spans = read_text_from_pdf(doc["path"], return_spans=True)
        blocks = smart_scene_blocks(text)
        for idx, block in enumerate(blocks):
            start = text.find(block)
            end = start + len(block)
            pages = page_range_for_span(page_spans, start, end)
            dialogues = extract_dialogues(block)
            scenes.append(Scene(
                id=f"S{idx+1}", index=idx, text=block.strip(),
                offset_start=start, offset_end=end,
                page_start=pages[0] if pages else None, page_end=pages[-1] if pages else None,
                dialogues=dialogues
            ))
    return scenes

def smart_scene_blocks(text: str) -> List[str]:
    # Разбиваем по заголовкам сцен или по крупным абзацам
    if SCENE_SPLIT_REGEX.search(text):
        parts = re.split(SCENE_SPLIT_REGEX, text)
        blocks = []
        buf = ""
        for p in parts:
            if p is None:
                continue
            if re.match(r"^(?:СЦЕНА\s+\d+|INT\.|EXT\.|ИНТ\.|НАТ\.|EXT\/INT\.|INT\/EXT\.)", p.strip(), re.IGNORECASE):
                if buf.strip():
                    blocks.append(buf.strip())
                buf = p
            else:
                buf += p
        if buf.strip():
            blocks.append(buf.strip())
        return [b for b in blocks if len(b.strip()) > 0]
    # fallback: по двойным переводам
    return [b for b in re.split(r"\n{2,}", text) if len(b.strip()) > 0]

def extract_dialogues(block: str):
    dialogues = []
    lines = [l.strip() for l in block.splitlines() if l.strip()]
    i = 0
    while i < len(lines):
        line = lines[i]
        if is_upper_name(line) and i + 1 < len(lines):
            dialogues.append({"character": line, "text": lines[i+1]})
            i += 2
        else:
            # диалог с тире
            m = re.match(r"^([A-ZА-ЯЁ][A-ZА-ЯЁ]+)\s*[:\-—]\s*(.+)$", line)
            if m:
                dialogues.append({"character": m.group(1), "text": m.group(2)})
            i += 1
    return dialogues

def is_upper_name(s: str) -> bool:
    s2 = re.sub(r"[^A-ZА-ЯЁ]", "", s)
    return len(s2) > 1 and s2 == s2.upper() and len(s.split()) <= 4

def page_range_for_span(page_spans, start, end):
    pages = set()
    for pidx, pstart, pend in page_spans:
        if pend < start: continue
        if pstart > end: break
        pages.add(pidx + 1)
    return sorted(list(pages))
