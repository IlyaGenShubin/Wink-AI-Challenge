import os
import re
import uuid
import yaml
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, List, Any, Optional
from app.models.schemas import Scene, Episode
from app.utils.text import normalize_text, deobfuscate_obscene, latin_to_cyr
from app.utils.io import read_yaml

CONFIG_PATH = "config/rules.yaml"

RULES = read_yaml(CONFIG_PATH)

SEVERITY_ORDER = ["None", "Mild", "Moderate", "Severe"]

def detect_in_scene(scene: Scene, rules: Dict[str, Any]) -> List[Episode]:
    text = scene.text
    norm = normalize_text(text)
    norm_deobf = deobfuscate_obscene(latin_to_cyr(norm))

    episodes: List[Episode] = []
    for cat, cfg in rules["categories"].items():
        cat_max = "None"
        cat_hits: List[Episode] = []

        def add_hit(sev: str, rule: str, span, quote, reason):
            cat_hits.append(Episode(
                id=str(uuid.uuid4())[:8],
                scene_id=scene.id,
                category=cat,
                severity=sev,
                rule_id=rule,
                start=span[0], end=span[1],
                quote=quote, reason=reason
            ))

        # patterns by severity
        for sev in ["severe", "moderate", "mild"]:
            pats = cfg.get("patterns", {}).get(sev, [])
            for p in pats:
                # ищем и в нормальном, и в деобфусцированном тексте
                for hay, tag in [(norm, "norm"), (norm_deobf, "deobf")]:
                    for m in re.finditer(p, hay, flags=re.IGNORECASE):
                        s, e = m.span()
                        quote = text[max(0, s-30):min(len(text), e+30)]
                        add_hit(sev.capitalize(), f"{cat}:{sev}:{p}:{tag}", (s, e), quote, f"match:{p}")

        # boosters
        boosters = cfg.get("boosters", {})
        for bsev, pats in boosters.items():
            for p in pats:
                if re.search(p, norm, flags=re.IGNORECASE) or re.search(p, norm_deobf, flags=re.IGNORECASE):
                    # повысить каждый hit до не ниже bsev
                    for h in cat_hits:
                        h.severity = max_severity(h.severity, bsev.capitalize())

        # анти‑FP (простая эвристика)
        for anti in cfg.get("anti_fp", []) or []:
            if re.search(anti, norm, flags=re.IGNORECASE):
                for h in cat_hits:
                    h.severity = "None"

        # итог по категории — берём все hits (для статистики)
        episodes.extend(cat_hits)

    return episodes

def process_scenes(scenes: List[Scene], prior_state: Optional[Dict[str, Any]] = None) -> Dict[str, List[Episode]]:
    # Инкрементально: если checksum одинаковый — берём прежние эпизоды
    out: Dict[str, List[Episode]] = {}
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = {}
        for sc in scenes:
            ch = checksum_scene(sc)
            if prior_state and prior_state.get(sc.id, {}).get("checksum") == ch:
                out[sc.id] = [Episode(**e) for e in prior_state[sc.id]["episodes"]]
            else:
                futures[pool.submit(detect_in_scene, sc, RULES)] = sc
        for fut, sc in futures.items():
            out[sc.id] = fut.result()
            out[sc.id] = [e for e in out[sc.id]]  # normalize
        # Обновим cache payload
        for sc in scenes:
            if sc.id not in out:
                out[sc.id] = []
    return out

def process_specific_scenes(scenes: List[Scene], scene_ids: List[str]) -> Dict[str, List[Episode]]:
    lookup = {s.id: s for s in scenes}
    out: Dict[str, List[Episode]] = {}
    for sid in scene_ids:
        sc = lookup[sid]
        out[sid] = detect_in_scene(sc, RULES)
    return out

def checksum_scene(scene: Scene) -> str:
    return str(abs(hash(scene.text)))

def max_severity(a: str, b: str) -> str:
    return a if SEVERITY_ORDER.index(a) >= SEVERITY_ORDER.index(b) else b
