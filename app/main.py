# app/main.py
import sys, asyncio, json
from uuid import uuid4
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

from fastapi import FastAPI, BackgroundTasks, HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import List, Dict, Any

from .automation import run_signup
from .logger import JobLogger
from .curp_utils import gen_email_from_curp, gen_password
from .utils import save_screenshot_blob

# Ensure Windows compatibility
if sys.platform.startswith("win"):
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

STORAGE = Path(__file__).parent / "storage"
STORAGE.mkdir(exist_ok=True)

app = FastAPI()
executor = ThreadPoolExecutor(max_workers=2)

# Serve static files (screenshots etc.)
app.mount("/static", StaticFiles(directory=STORAGE), name="static")

JOBS: Dict[str, Dict[str, Any]] = {}


class JobRequest(BaseModel):
    curp: str


@app.post("/jobs")
async def create_job(req: JobRequest, background_tasks: BackgroundTasks):
    job_id = str(uuid4())
    email = gen_email_from_curp(req.curp)
    password = gen_password()
    log_path = STORAGE / f"{job_id}.log.jsonl"

    job = {
        "job_id": job_id,
        "curp": req.curp,
        "email": email,
        "password": password,
        "status": "queued",
        "logs": [],
        "created_account": {
            "email": email,
            "password": password,
            "creation_status": "pending"
        },
        "captcha_screenshot": None,
        "user_data_dir": str(STORAGE / f"{job_id}_profile"),
        "step_index": 0,
        "logs_raw": [],
    }
    JOBS[job_id] = job

    def _run():
        logger = JobLogger(str(log_path))
        try:
            result = run_signup(job_id, email, password, logger, headless=False)
            job["logs"] = logger.entries
            job["logs_raw"] = [json.dumps(e, ensure_ascii=False) for e in job["logs"]]
            job["status"] = result["status"]
            job["created_account"]["creation_status"] = (
                "success" if result["status"] == "completed" else result["status"]
            )
            if result.get("screenshot"):
                out_path = STORAGE / f"{job_id}_captcha.png"
                job["captcha_screenshot"] = save_screenshot_blob(result["screenshot"], out_path)
        except Exception as e:
            logger.log("fatal_error", False, f"{e}")
            job["status"] = "failed"

    executor.submit(_run)
    return {"job_id": job_id, "status": "queued"}


@app.get("/jobs/{job_id}")
async def get_job(job_id: str):
    job = JOBS.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="job not found")
    return job


@app.post("/jobs/{job_id}/resume")
async def resume_job(job_id: str):
    job = JOBS.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="job not found")
    if job["status"] != "waiting_for_human":
        raise HTTPException(
            status_code=400,
            detail=f"Job not in waiting_for_human state (current={job['status']})"
        )

    def _resume():
        log_path = STORAGE / f"{job_id}.log.jsonl"
        logger = JobLogger(str(log_path))
        try:
            result = run_signup(job_id, job["email"], job["password"], logger, headless=False)
            job["logs"] = logger.entries
            job["logs_raw"] = [json.dumps(e, ensure_ascii=False) for e in job["logs"]]
            job["status"] = result["status"]
            job["created_account"]["creation_status"] = (
                "success" if result["status"] == "completed" else result["status"]
            )
            if result.get("screenshot"):
                out_path = STORAGE / f"{job_id}_captcha_resume.png"
                job["captcha_screenshot"] = save_screenshot_blob(result["screenshot"], out_path)
        except Exception as e:
            logger.log("resume_exception", False, str(e))
            job["status"] = "failed"

    executor.submit(_resume)
    return {"job_id": job_id, "status": "resuming"}
