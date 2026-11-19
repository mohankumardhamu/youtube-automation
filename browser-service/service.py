"""Local VEED browser-automation service for the n8n workflow.

Runs on the host (not in Docker) because it needs a display and your saved VEED login.
n8n reaches it at http://host.docker.internal:8765.

The API matches the fal.ai queue API, so the n8n polling nodes work unchanged:
  POST /veed/jobs                      {"script": "...", "title": "..."} -> {request_id, status_url, response_url}
  GET  /veed/jobs/{id}/status?token=   -> {"status": "IN_QUEUE" | "IN_PROGRESS" | "COMPLETED"}  (failed jobs report COMPLETED)
  GET  /veed/jobs/{id}?token=          -> {"video": {"url": ..., "content_type": "video/mp4"}}  (HTTP 500 if failed)
  GET  /files/{id}.mp4?token=          -> the MP4
"""
from __future__ import annotations

import os
import pathlib
import queue
import threading
import time
import traceback
import uuid

from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

import veed_flow

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
AUTH_FILE = HERE / "auth" / "veed.json"
OUT_DIR = HERE / "output"
DEBUG_DIR = HERE / "debug"


def load_env(path: pathlib.Path) -> None:
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())


load_env(ROOT / ".env")
TOKEN = os.environ.get("BROWSER_SERVICE_TOKEN", "")
PUBLIC_BASE = os.environ.get("BROWSER_SERVICE_PUBLIC_URL", "http://host.docker.internal:8765").rstrip("/")
HEADLESS = os.environ.get("BROWSER_HEADLESS", "false").lower() == "true"
JOB_TIMEOUT_S = int(os.environ.get("VEED_JOB_TIMEOUT_MIN", "28")) * 60

if not TOKEN:
    raise SystemExit("BROWSER_SERVICE_TOKEN is not set in ../.env")

OUT_DIR.mkdir(exist_ok=True)
DEBUG_DIR.mkdir(exist_ok=True)

jobs: dict[str, dict] = {}
work: "queue.Queue[str]" = queue.Queue()
app = FastAPI(title="VEED browser service")


def check(token: str | None) -> None:
    if token != TOKEN:
        raise HTTPException(status_code=401, detail="bad token")


def worker() -> None:
    from playwright.sync_api import sync_playwright

    with sync_playwright() as pw:
        while True:
            job_id = work.get()
            job = jobs[job_id]
            job["status"] = "IN_PROGRESS"
            job["started"] = time.time()
            browser = context = None
            try:
                if not AUTH_FILE.exists():
                    raise RuntimeError("No saved VEED login. Run ./record.sh and log in first.")
                browser = pw.firefox.launch(headless=HEADLESS)
                context = browser.new_context(
                    storage_state=str(AUTH_FILE), accept_downloads=True,
                    viewport={"width": 1440, "height": 900},
                )
                context.set_default_timeout(60_000)
                page = context.new_page()
                out = OUT_DIR / f"{job_id}.mp4"
                veed_flow.run(page, job["script"], job["title"], out, deadline=job["started"] + JOB_TIMEOUT_S)
                if not out.exists() or out.stat().st_size < 10_000:
                    raise RuntimeError("Flow finished but no MP4 was saved")
                context.storage_state(path=str(AUTH_FILE))  # keep the session fresh
                job["status"] = "COMPLETED"
            except Exception as e:  # noqa: BLE001
                job["status"] = "FAILED"
                job["error"] = f"{type(e).__name__}: {e}"[:1000]
                traceback.print_exc()
                try:
                    if context and context.pages:
                        context.pages[0].screenshot(path=str(DEBUG_DIR / f"{job_id}.png"), full_page=True)
                except Exception:  # noqa: BLE001
                    pass
            finally:
                for closer in (context, browser):
                    try:
                        closer and closer.close()
                    except Exception:  # noqa: BLE001
                        pass
                job["finished"] = time.time()


threading.Thread(target=worker, daemon=True).start()


class JobIn(BaseModel):
    script: str
    title: str = ""


@app.get("/health")
def health():
    return {"ok": True, "logged_in": AUTH_FILE.exists(), "queued": work.qsize()}


@app.post("/veed/jobs")
def create_job(body: JobIn, authorization: str | None = Header(default=None), x_token: str | None = Header(default=None)):
    supplied = x_token or (authorization or "").removeprefix("Key ").removeprefix("Bearer ")
    check(supplied)
    if not body.script.strip():
        raise HTTPException(400, "script is empty")
    job_id = uuid.uuid4().hex
    jobs[job_id] = {"status": "IN_QUEUE", "script": body.script, "title": body.title, "created": time.time()}
    work.put(job_id)
    base = f"{PUBLIC_BASE}/veed/jobs/{job_id}"
    return {"request_id": job_id, "status_url": f"{base}/status?token={TOKEN}", "response_url": f"{base}?token={TOKEN}"}


def get_job(job_id: str) -> dict:
    if job_id not in jobs:
        raise HTTPException(404, "unknown job (the service may have restarted)")
    return jobs[job_id]


@app.get("/veed/jobs/{job_id}/status")
def job_status(job_id: str, token: str = ""):
    check(token)
    job = get_job(job_id)
    # Like fal.ai: a failed job reports COMPLETED here; the result endpoint then returns the error,
    # so n8n stops polling straight away and logs the URL as skipped.
    status = "COMPLETED" if job["status"] == "FAILED" else job["status"]
    return {"status": status, "state": job["status"], "error": job.get("error")}


@app.get("/veed/jobs/{job_id}")
def job_result(job_id: str, token: str = ""):
    check(token)
    job = get_job(job_id)
    if job["status"] == "FAILED":
        raise HTTPException(500, job.get("error", "failed"))
    if job["status"] != "COMPLETED":
        raise HTTPException(409, f"job is {job['status']}")
    return {"video": {"url": f"{PUBLIC_BASE}/files/{job_id}.mp4?token={TOKEN}", "content_type": "video/mp4"}}


@app.get("/files/{name}")
def files(name: str, token: str = ""):
    check(token)
    path = (OUT_DIR / name).resolve()
    if path.parent != OUT_DIR.resolve() or not path.exists():
        raise HTTPException(404, "not found")
    return FileResponse(path, media_type="video/mp4")
