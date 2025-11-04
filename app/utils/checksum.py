import hashlib

def file_checksum(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()

def text_checksum(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()
