from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
import orjson

class Scene(BaseModel):
    id: str
    index: int
    text: str
    offset_start: int
    offset_end: int
    page_start: Optional[int] = None
    page_end: Optional[int] = None
    dialogues: List[Dict[str, str]] = Field(default_factory=list)  # {"character": "ИВАН", "text": "Привет!"}

class Episode(BaseModel):
    id: str
    scene_id: str
    category: str
    severity: str  # None/Mild/Moderate/Severe
    rule_id: str
    start: int
    end: int
    quote: str
    reason: str
    is_manual: bool = False
    is_fp: bool = False

class SummaryCategory(BaseModel):
    category: str
    count_episodes: int
    percent_scenes: float
    overall_severity: str  # None/Mild/Moderate/Severe

class Summary(BaseModel):
    total_scenes: int
    categories: List[SummaryCategory]
    max_severity: str
    age_rating: str

class AnalysisResult(BaseModel):
    file_id: str
    filename: str
    checksum: str
    scenes: List[Scene]
    episodes: List[Episode]
    summary: Optional[Summary] = None

class ManualEpisode(BaseModel):
    file_id: str
    scene_id: str
    category: str
    severity: str
    quote: str
    reason: str
    start: int = 0
    end: int = 0

class PatchRequest(BaseModel):
    file_id: str
    edits: List[Dict[str, Any]]  # [{"scene_id": "S1", "new_text": "..."}]

# orjson helpers
def orjson_dumps(v, *, default):
    return orjson.dumps(v, default=default).decode()

AnalysisResult.model_rebuild()
