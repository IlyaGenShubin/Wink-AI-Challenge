import os
import json
from typing import Dict, Any, Optional
from app.models.schemas import Episode

def cache_path(base: str, file_id: str) -> str:
    return os.path.join(base, f"{file_id}.cache.json")

def load_cache(base: str, file_id: str) -> Optional[Dict[str, Any]]:
    p = cache_path(base, file_id)
    if not os.path.exists(p):
        return None
    with open(p, "r", encoding="utf-8") as f:
        return json.load(f)

def save_cache(base: str, file_id: str, episodes_by_scene: Dict[str, Any]):
    p = cache_path(base, file_id)
    payload = {}
    for sid, eps in episodes_by_scene.items():
        payload[sid] = {
            "checksum": str(abs(hash("".join([e.quote for e in eps])))),  # дешёвый checksum по эпизодам
            "episodes": [e.model_dump() for e in eps]
        }
    with open(p, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
