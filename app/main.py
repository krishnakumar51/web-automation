# app/main.py
import sys, asyncio, json
from uuid import uuid4
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

from fastapi import FastAPI, BackgroundTasks, HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import List, Dict, Any

from .automation import run_signup, resume_signup, cleanup_context
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
        "browser_open": False
    }
    JOBS[job_id] = job

    def _run():
        logger = JobLogger(job_id)
        job["status"] = "running"
        job["browser_open"] = True
        
        try:
            logger.log("job_start", True, f"Starting signup for {email}")
            result = run_signup(job_id, email, password, logger, headless=False)
            
            job["logs"] = logger.entries
            job["logs_raw"] = [json.dumps(e, ensure_ascii=False) for e in job["logs"]]
            job["status"] = result["status"]
            
            # Update account creation status
            if result["status"] == "completed":
                job["created_account"]["creation_status"] = "success"
                job["browser_open"] = False
            elif result["status"] == "waiting_for_human":
                job["created_account"]["creation_status"] = "waiting_for_captcha"
                job["browser_open"] = True  # Browser stays open for CAPTCHA
            else:
                job["created_account"]["creation_status"] = result["status"]
                job["browser_open"] = False
            
            # Save screenshot if available
            if result.get("screenshot"):
                out_path = STORAGE / f"{job_id}_captcha.png"
                screenshot_url = save_screenshot_blob(result["screenshot"], out_path)
                job["captcha_screenshot"] = screenshot_url
                
        except Exception as e:
            logger.log("fatal_error", False, f"{e}")
            job["status"] = "failed"
            job["browser_open"] = False
            job["created_account"]["creation_status"] = "failed"

    executor.submit(_run)
    return {"job_id": job_id, "status": "queued", "email": email}


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
        logger = JobLogger(job_id)
        job["status"] = "resuming"
        
        try:
            logger.log("resume_start", True, "Resuming job from human intervention")
            result = resume_signup(job_id, logger)
            
            # Append new logs to existing ones
            job["logs"].extend(logger.entries)
            job["logs_raw"].extend([json.dumps(e, ensure_ascii=False) for e in logger.entries])
            job["status"] = result["status"]
            
            # Update account status
            if result["status"] == "completed":
                job["created_account"]["creation_status"] = "success"
                job["browser_open"] = False
            elif result["status"] == "waiting_for_human":
                job["created_account"]["creation_status"] = "still_waiting_for_captcha"
                job["browser_open"] = True
            else:
                job["created_account"]["creation_status"] = result["status"]
                job["browser_open"] = False
            
            # Save resume screenshot if available
            if result.get("screenshot"):
                out_path = STORAGE / f"{job_id}_captcha_resume.png"
                screenshot_url = save_screenshot_blob(result["screenshot"], out_path)
                job["captcha_screenshot"] = screenshot_url
                
        except Exception as e:
            logger.log("resume_exception", False, str(e))
            job["status"] = "failed"
            job["browser_open"] = False
            job["created_account"]["creation_status"] = "resume_failed"

    executor.submit(_resume)
    return {"job_id": job_id, "status": "resuming"}


@app.delete("/jobs/{job_id}/browser")
async def close_browser(job_id: str):
    """Manually close the browser context for a job."""
    job = JOBS.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="job not found")
    
    try:
        cleanup_context(job_id)
        job["browser_open"] = False
        return {"job_id": job_id, "message": "Browser closed"}
    except Exception as e:
        return {"job_id": job_id, "error": str(e)}


@app.get("/jobs")
async def list_jobs():
    """List all jobs with basic info."""
    return {
        "jobs": [
            {
                "job_id": job["job_id"],
                "status": job["status"],
                "email": job["email"],
                "browser_open": job.get("browser_open", False),
                "creation_status": job["created_account"]["creation_status"]
            }
            for job in JOBS.values()
        ]
    }


@app.on_event("shutdown")
async def shutdown_event():
    """Clean up all browser contexts on shutdown."""
    from .automation import _active_contexts
    for job_id in list(_active_contexts.keys()):
        try:
            cleanup_context(job_id)
        except Exception:
            pass