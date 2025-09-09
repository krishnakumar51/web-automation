# app/models.py
from pydantic import BaseModel
from typing import List, Optional, Dict, Any

class JobRequest(BaseModel):
    curps: List[str]

class LogEntry(BaseModel):
    timestamp: str
    step: str
    success: bool
    message: str
    extra: Optional[Dict[str, Any]] = None

class JobResult(BaseModel):
    job_id: str
    status: str  # queued, running, waiting_for_human, completed, failed
    created_account: Optional[Dict[str, str]] = None
    logs: List[LogEntry] = []
    captcha_screenshot: Optional[str] = None
