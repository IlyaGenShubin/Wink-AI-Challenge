import os
import uuid
from typing import Dict, List, Any
import yaml
from app.models.schemas import AnalysisResult, Scene, Episode, Summary, SummaryCategory, ManualEpisode, PatchRequest
from app.utils.checksum import file_checksum
from app.utils.io import read_yaml

AGE_MAP = read_yaml("config/age_mapping.yaml")
SEV_ORDER = ["None", "Mild", "Moderate", "Severe"]

def build_analysis(file_id: str, filename_path: str, scenes: List[Scene], episodes_by_scene: Dict[str, List[Episode]]) -> AnalysisResult:
    checksum = file_checksum(filename_path)
    episodes: List[Episode] = []
    for sid, eps in episodes_by_scene.items():
        episodes.extend(eps)
    return AnalysisResult(
        file_id=file_id,
        filename=os.path.basename(filename_path),
        checksum=checksum,
        scenes=scenes,
        episodes=episodes,
        summary=None
    )

def apply_manual_adjustments(analysis: AnalysisResult):
    # помеченные is_fp — исключаем из расчёта; manual episodes — включаются
    pass  # episodes уже содержат is_fp/is_manual; фильтруем при подсчёте

def severity_for_category(episodes: List[Episode], category: str) -> str:
    sev = "None"
    for e in episodes:
        if e.category != category or e.is_fp:
            continue
        if SEV_ORDER.index(e.severity) > SEV_ORDER.index(sev):
            sev = e.severity
    return sev

def compute_summary_and_rating(analysis: AnalysisResult):
    cats = sorted(set(e.category for e in analysis.episodes))
    per_cat: List[SummaryCategory] = []
    total_scenes = len(analysis.scenes)
    for c in cats:
        eps = [e for e in analysis.episodes if e.category == c and not e.is_fp]
        scenes_hit = len(set(e.scene_id for e in eps))
        sev = severity_for_category(analysis.episodes, c)
        per_cat.append(SummaryCategory(
            category=c,
            count_episodes=len(eps),
            percent_scenes=round((scenes_hit / max(1, total_scenes)) * 100, 2),
            overall_severity=sev
        ))
    # максимальная строгость и возрастной рейтинг
    max_sev = "None"
    max_cat = None
    for sc in per_cat:
        if SEV_ORDER.index(sc.overall_severity) > SEV_ORDER.index(max_sev):
            max_sev = sc.overall_severity
            max_cat = sc.category
    age = map_age_rating(max_cat, max_sev)
    analysis.summary = Summary(
        total_scenes=total_scenes,
        categories=per_cat,
        max_severity=max_sev,
        age_rating=age
    )

def map_age_rating(category: str, severity: str) -> str:
    if not category:
        return AGE_MAP["default"].get("None", "0+")
    ovr = AGE_MAP.get("overrides", {}).get(category, {})
    return ovr.get(severity, AGE_MAP["default"].get(severity, "0+"))

def apply_patch(analysis: AnalysisResult, req: PatchRequest) -> List[str]:
    changed = []
    scindex = {s.id: s for s in analysis.scenes}
    for edit in req.edits:
        sid = edit["scene_id"]
        new_text = edit["new_text"]
        if sid in scindex:
            scindex[sid].text = new_text
            changed.append(sid)
    return changed

def merge_scene_episodes(analysis: AnalysisResult, updated: Dict[str, List[Episode]]):
    # Удаляем старые эпизоды для изменённых сцен и добавляем новые
    keep = [e for e in analysis.episodes if e.scene_id not in updated]
    for sid, eps in updated.items():
        keep.extend(eps)
    analysis.episodes = keep

def mark_false_positive(analysis: AnalysisResult, episode_id: str):
    for e in analysis.episodes:
        if e.id == episode_id:
            e.is_fp = True

def add_manual_episode(analysis: AnalysisResult, req: ManualEpisode):
    analysis.episodes.append(
        Episode(
            id=str(uuid.uuid4())[:8],
            scene_id=req.scene_id,
            category=req.category,
            severity=req.severity,
            rule_id="manual",
            start=req.start,
            end=req.end,
            quote=req.quote,
            reason=req.reason,
            is_manual=True,
            is_fp=False
        )
    )
