import re
import json

def normalize_text(s: str) -> str:
    s = s.replace("\r", "\n")
    s = re.sub(r"\s+", " ", s)
    s = s.lower()
    s = s.replace("ё", "е")
    return s

LATIN_TO_CYR = str.maketrans({
    "a":"а","e":"е","o":"о","p":"р","c":"с","x":"х","y":"у","k":"к","h":"н","m":"м","t":"т","b":"в"
})

def latin_to_cyr(s: str) -> str:
    return s.translate(LATIN_TO_CYR)

def deobfuscate_obscene(s: str) -> str:
    # Убираем пробелы/символы между буквами, звёздочки/цифры в неприличных словах
    s = re.sub(r"[\*\-\_\.\,\/\\\|\(\)\[\]\{\}\+\=\~\^\`\'\"\:]+", "", s)
    s = re.sub(r"\d", "", s)
    return s

def safe_json_dump(obj, path: str):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
