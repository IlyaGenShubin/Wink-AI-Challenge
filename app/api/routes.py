import uuid
import os
from typing import Optional, Dict, Any, List

from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.templating import Jinja2Templates

from app.services import parser, detector, aggregate, report, cache
from app.models.schemas import AnalysisResult, ManualEpisode, PatchRequest
from app.utils.io import read_file_bytes, ensure_dirs
from app.utils.checksum import file_checksum
from app.utils.text import safe_json_dump

TEMPLATES = Jinja2Templates(directory="app/templates")
router = APIRouter()

DATA_DIR = "data"
UPLOADS = os.path.join(DATA_DIR, "uploads")
ANALYSES = os.path.join(DATA_DIR, "analyses")
REPORTS = os.path.join(DATA_DIR, "reports")
CACHE = os.path.join(DATA_DIR, "cache")
ensure_dirs([UPLOADS, ANALYSES, REPORTS, CACHE])

@router.post("/upload", response_class=HTMLResponse)
async def upload(request: Request, file: UploadFile = File(...)):
    file_id = str(uuid.uuid4())
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in [".pdf", ".docx"]:
        raise HTTPException(400, "Поддерживаются только .pdf и .docx")

    dst = os.path.join(UPLOADS, f"{file_id}{ext}")
    content = await file.read()
    with open(dst, "wb") as f:
        f.write(content)

    return TEMPLATES.TemplateResponse("results.html", {
        "request": request,
        "file_id": file_id,
        "filename": file.filename,
        "analysis": None,
        "summary": None,
        "message": "Файл загружен. Запустите анализ."
    })

@router.post("/analyze", response_class=HTMLResponse)
async def analyze(request: Request, file_id: str = Form(...)):
    # Найдём файл
    upload = None
    for name in os.listdir(UPLOADS):
        if name.startswith(file_id):
            upload = os.path.join(UPLOADS, name)
            break
    if not upload:
        raise HTTPException(404, "Файл не найден")

    # Парсинг и сегментация
    doc = parser.load_document(upload)
    scenes = parser.segment_scenes(doc)

    # Инкрементальная обработка по checksum сцен
    prior_state = cache.load_cache(CACHE, file_id)
    episodes_by_scene = detector.process_scenes(scenes, prior_state=prior_state)

    # Агрегация
    analysis = aggregate.build_analysis(file_id, upload, scenes, episodes_by_scene)
    aggregate.apply_manual_adjustments(analysis)  # если были FP/FN/редакции
    aggregate.compute_summary_and_rating(analysis)  # финальные метрики и рейтинг

    # Сохранение результатов и кеш
    cache.save_cache(CACHE, file_id, episodes_by_scene)
    out_path = os.path.join(ANALYSES, f"{file_id}.json")
    safe_json_dump(analysis.model_dump(), out_path)

    return TEMPLATES.TemplateResponse("results.html", {
        "request": request,
        "file_id": file_id,
        "filename": os.path.basename(upload),
        "analysis": analysis.model_dump(),
        "summary": analysis.summary
    })

@router.post("/patch", response_class=JSONResponse)
async def patch(req: PatchRequest):
    file_id = req.file_id
    analysis_path = os.path.join(ANALYSES, f"{file_id}.json")
    if not os.path.exists(analysis_path):
        raise HTTPException(404, "Анализ для файла не найден")

    # Применяем правки
    analysis = AnalysisResult.model_validate_json(open(analysis_path, "r", encoding="utf-8").read())

    changed_scene_ids = aggregate.apply_patch(analysis, req)
    # Переоценка только изменённых сцен
    scenes = analysis.scenes
    updated_episodes = detector.process_specific_scenes(scenes, changed_scene_ids)

    # Объединяем новую оценку
    aggregate.merge_scene_episodes(analysis, updated_episodes)
    aggregate.apply_manual_adjustments(analysis)
    aggregate.compute_summary_and_rating(analysis)

    safe_json_dump(analysis.model_dump(), analysis_path)
    return JSONResponse({"status": "ok", "changed_scenes": changed_scene_ids, "summary": analysis.summary})

@router.post("/mark-fp", response_class=JSONResponse)
async def mark_fp(file_id: str = Form(...), episode_id: str = Form(...)):
    path = os.path.join(ANALYSES, f"{file_id}.json")
    if not os.path.exists(path):
        raise HTTPException(404, "Нет анализа")
    analysis = AnalysisResult.model_validate_json(open(path, "r", encoding="utf-8").read())
    aggregate.mark_false_positive(analysis, episode_id)
    aggregate.compute_summary_and_rating(analysis)
    safe_json_dump(analysis.model_dump(), path)
    return JSONResponse({"status": "ok", "summary": analysis.summary})

@router.post("/add-episode", response_class=JSONResponse)
async def add_episode(req: ManualEpisode):
    path = os.path.join(ANALYSES, f"{req.file_id}.json")
    if not os.path.exists(path):
        raise HTTPException(404, "Нет анализа")
    analysis = AnalysisResult.model_validate_json(open(path, "r", encoding="utf-8").read())
    aggregate.add_manual_episode(analysis, req)
    aggregate.compute_summary_and_rating(analysis)
    safe_json_dump(analysis.model_dump(), path)
    return JSONResponse({"status": "ok", "summary": analysis.summary})

@router.get("/report/html/{file_id}", response_class=FileResponse)
def report_html(file_id: str):
    analysis_path = os.path.join(ANALYSES, f"{file_id}.json")
    if not os.path.exists(analysis_path):
        raise HTTPException(404, "Нет анализа")
    analysis = AnalysisResult.model_validate_json(open(analysis_path, "r", encoding="utf-8").read())
    html_path = report.render_html(analysis)
    return FileResponse(html_path, media_type="text/html", filename=os.path.basename(html_path))

@router.get("/report/pdf/{file_id}", response_class=FileResponse)
def report_pdf(file_id: str):
    analysis_path = os.path.join(ANALYSES, f"{file_id}.json")
    if not os.path.exists(analysis_path):
        raise HTTPException(404, "Нет анализа")
    analysis = AnalysisResult.model_validate_json(open(analysis_path, "r", encoding="utf-8").read())
    pdf_path = report.render_pdf(analysis)
    return FileResponse(pdf_path, media_type="application/pdf", filename=os.path.basename(pdf_path))
