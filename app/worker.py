# app/worker.py
import threading, queue, uuid, time
from .logger import JobLogger
from .curp_utils import gen_email_from_curp, gen_password
from .automation import run_signup

JOB_QUEUE = queue.Queue()
JOBS = {}  # job_id -> dict

_worker_thread = None

def _worker_loop():
    while True:
        job_data = JOB_QUEUE.get()
        if job_data is None:
            break
        job_id = job_data["job_id"]
        curp = job_data["curp"]

        logger = JobLogger(job_id)
        JOBS[job_id] = {
            "job_id": job_id,
            "status": "running",
            "logs": [],
            "created_account": None,
            "captcha_screenshot": None,
            "user_data_dir": str(logger.path.parent / f"{job_id}_profile"),
            "step_index": 0
        }

        try:
            email = gen_email_from_curp(curp)
            pwd = gen_password()
            logger.log("gen_credentials", True, f"email={email}")
            # Run automation
            res = run_signup(job_id, email, pwd, logger, headless=False)
            # update JOBS
            JOBS[job_id]["logs"] = logger.entries
            if res["status"] == "waiting_for_human":
                JOBS[job_id]["status"] = "waiting_for_human"
                # save screenshot path (already saved in logger.save_screenshot inside automation)
                JOBS[job_id]["captcha_screenshot"] = logger.path.parent / f"{job_id}_captcha.png"
                JOBS[job_id]["created_account"] = {
                    "email": email,
                    "password": pwd,
                    "creation_status": "blocked_by_captcha",
                    "creation_timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ")
                }
            elif res["status"] == "completed":
                JOBS[job_id]["status"] = "completed"
                JOBS[job_id]["created_account"] = {
                    "email": email,
                    "password": pwd,
                    "creation_status": "success",
                    "creation_timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ")
                }
                JOBS[job_id]["captcha_screenshot"] = None
            else:
                JOBS[job_id]["status"] = "failed"
                JOBS[job_id]["created_account"] = {
                    "email": email,
                    "password": pwd,
                    "creation_status": "failed"
                }
        except Exception as e:
            logger.log("worker_exception", False, f"{e}")
            JOBS[job_id]["status"] = "failed"
            JOBS[job_id]["logs"] = logger.entries
        JOB_QUEUE.task_done()

def start_worker():
    global _worker_thread
    if _worker_thread is None:
        _worker_thread = threading.Thread(target=_worker_loop, daemon=True)
        _worker_thread.start()

def submit_job(curp: str):
    job_id = str(uuid.uuid4())
    JOB_QUEUE.put({"job_id": job_id, "curp": curp})
    JOBS[job_id] = {"job_id": job_id, "status": "queued", "logs": [], "created_account": None, "captcha_screenshot": None}
    return job_id
