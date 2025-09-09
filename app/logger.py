# app/logger.py
import json
from datetime import datetime
from pathlib import Path

STORAGE = Path(__file__).parent / "storage"
STORAGE.mkdir(parents=True, exist_ok=True)

def now_iso():
    return datetime.utcnow().isoformat() + "Z"

class JobLogger:
    def __init__(self, job_id: str):
        self.job_id = job_id
        self.path = STORAGE / f"{job_id}.log.jsonl"
        self.entries = []

    def log(self, step: str, success: bool, message: str, extra: dict = None):
        entry = {
            "timestamp": now_iso(),
            "step": step,
            "success": success,
            "message": message,
            "extra": extra or {}
        }
        self.entries.append(entry)
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        return entry

    def save_screenshot(self, img_bytes: bytes, name_suffix="captcha.png"):
        out = STORAGE / f"{self.job_id}_{name_suffix}"
        with open(out, "wb") as f:
            f.write(img_bytes)
        return str(out)
