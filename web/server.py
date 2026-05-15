"""FastAPI backend – dual-mode ERPNext COA Converter.

Supports both Commercial (s.r.o., default) and Public Sector (Státní pokladna)
modes via FIFO job queue with SSE progress streaming.
"""

import asyncio
import contextlib
import csv
import io
import json
import os
import shutil
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional, Tuple
from uuid import uuid4

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, StreamingResponse

import xml.etree.ElementTree as ET

import erpnext_coa_translator as converter
import translation_engine as te

STATIC_DIR = Path(__file__).parent / "static"

MAX_UPLOAD_MB = int(os.getenv("MAX_UPLOAD_MB", "20"))
MAX_UPLOAD_BYTES = MAX_UPLOAD_MB * 1024 * 1024
MAX_JOBS = int(os.getenv("MAX_JOBS", "100"))
MAX_QUEUE = int(os.getenv("MAX_QUEUE", "50"))
JOB_TTL_SECONDS = int(os.getenv("JOB_TTL_SECONDS", "3600"))


@dataclass
class JobState:
    id: str
    status: str  # queued|running|done|error
    created_at: float
    input_name: str
    settings: Dict[str, Any]
    input_ext: str
    mode: str  # commercial | public_sector
    uploaded_bytes: Optional[bytes] = None
    output_path: Optional[str] = None
    work_dir: Optional[str] = None
    error: Optional[str] = None
    events: Optional[asyncio.Queue] = None
    api_key: Optional[str] = None


app = FastAPI(title="ERPNext COA Converter")

_job_queue: "asyncio.Queue[str]" = asyncio.Queue()
_jobs: Dict[str, JobState] = {}
_worker_started = False


@app.get("/api/health")
async def health():
    return {
        "status": "ok",
        "queued": _job_queue.qsize(),
        "jobs": len(_jobs),
        "max_upload_mb": MAX_UPLOAD_MB,
    }


def _safe_config(cfg: Dict[str, Any]) -> Dict[str, Any]:
    redacted = dict(cfg or {})
    for k in list(redacted.keys()):
        if "key" in k.lower():
            redacted[k] = "***"
    return redacted


def _cleanup_old_jobs(now: float) -> None:
    to_delete = [
        jid for jid, j in _jobs.items()
        if j.status in ("done", "error") and (now - j.created_at) > JOB_TTL_SECONDS
    ]
    for jid in to_delete:
        job = _jobs.pop(jid, None)
        if job and job.work_dir:
            with contextlib.suppress(Exception):
                shutil.rmtree(job.work_dir, ignore_errors=True)


def _detect_input_kind(content: bytes) -> Tuple[str, str]:
    if not content:
        raise HTTPException(status_code=400, detail="Empty file")
    sniff = content[:4096].lstrip()

    # XML
    if sniff.startswith(b"<"):
        try:
            root = ET.fromstring(content)
            if root.find("row") is not None:
                return "xml", ".xml"
        except Exception:
            pass

    # CSV detection
    try:
        text = content.decode("utf-8", errors="strict")
    except Exception:
        raise HTTPException(status_code=400, detail="Unsupported encoding")

    reader = csv.DictReader(io.StringIO(text), delimiter=";")
    headers = set(reader.fieldnames or [])

    # Public sector CSV
    ps_headers = {
        "/BIC/ZC_VYKAZ Výkaz",
        "/BIC/ZC_POLVYK Položka výkazu",
        "/BIC/ZC_SYNUC Syntetický účet",
        "DATETO Platí do",
        "TXTXL Dlouhý text",
    }
    if ps_headers.issubset(headers):
        return "cis_polvyk_csv", ".csv"

    # Commercial CSV (comma-delimited)
    reader2 = csv.DictReader(io.StringIO(text))
    headers2 = set(reader2.fieldnames or [])
    comm_headers = {"account_number", "name_cz", "account_class"}
    if comm_headers.issubset(headers2):
        return "commercial_csv", ".csv"

    raise HTTPException(status_code=400, detail="Unrecognized file format")


def _sse_pack(event: Dict[str, Any]) -> bytes:
    return ("data: " + json.dumps(event, ensure_ascii=False) + "\n\n").encode("utf-8")


async def _emit(job: JobState, event: Dict[str, Any]):
    if not job.events:
        return
    try:
        job.events.put_nowait(event)
    except asyncio.QueueFull:
        pass


def _apply_runtime_config(cfg: Dict[str, Any], api_key: str) -> None:
    te.TRANSLATE_ENABLED = bool(cfg.get("translate_enabled", False))
    raw_langs = (cfg.get("translate_langs", "") or "").strip()
    te.RAW_TRANSLATE_LANGS = raw_langs
    te.TRANSLATE_LANGS = te.validate_translation_settings(
        te.TRANSLATE_ENABLED,
        te.parse_lang_codes(raw_langs if raw_langs else ",".join(te.DEFAULT_LANGS)),
    )
    te.TARGET_LANGS = te.TRANSLATE_LANGS if te.TRANSLATE_ENABLED else []

    converter.CURRENCY = cfg.get("currency") or converter.CURRENCY
    te.LIMIT = int(cfg.get("limit") or te.LIMIT)
    converter.OUTPUT_PREFIX = cfg.get("output_prefix") or converter.OUTPUT_PREFIX

    te.MAX_WORKERS = int(cfg.get("max_workers") or te.MAX_WORKERS)
    te.BATCH_SIZE = int(cfg.get("batch_size") or te.BATCH_SIZE)

    provider = (cfg.get("provider") or te.PROVIDER).lower()
    te.PROVIDER = provider

    model = (cfg.get("model") or "").strip()
    if provider == "siliconflow":
        te.SILICONFLOW_API_KEY = api_key
        if model:
            te.MODEL_ID = model
    elif provider == "openrouter":
        te.OPENROUTER_API_KEY = api_key
        if model:
            te.OPENROUTER_MODEL = model
    elif provider == "openai":
        te.OPENAI_API_KEY = api_key
        if model:
            te.OPENAI_MODEL = model
    elif provider == "gemini":
        te.GEMINI_API_KEY = api_key
        if model:
            te.GEMINI_MODEL = model

    # Rebuild provider map
    te.PROVIDERS = {
        "siliconflow": {
            "api_key": te.SILICONFLOW_API_KEY,
            "model": te.MODEL_ID,
            "base_url": "https://api.siliconflow.cn/v1",
            "extra_headers": None,
        },
        "openrouter": {
            "api_key": te.OPENROUTER_API_KEY,
            "model": te.OPENROUTER_MODEL,
            "base_url": "https://openrouter.ai/api/v1",
            "extra_headers": {"X-Title": "ERPNext Czech COA Converter"},
        },
        "openai": {
            "api_key": te.OPENAI_API_KEY,
            "model": te.OPENAI_MODEL,
            "base_url": "https://api.openai.com/v1",
            "extra_headers": None,
        },
        "gemini": {
            "api_key": te.GEMINI_API_KEY,
            "model": te.GEMINI_MODEL,
            "base_url": "https://generativelanguage.googleapis.com/v1beta/openai",
            "extra_headers": None,
        },
    }


async def _worker_loop():
    while True:
        job_id = await _job_queue.get()
        job = _jobs.get(job_id)
        if not job:
            continue

        job.status = "running"
        await _emit(job, {"type": "status", "status": job.status})

        try:
            tmp_dir = Path(tempfile.mkdtemp(prefix=f"erpnext_coa_{job.id}_"))
            job.work_dir = str(tmp_dir)
            output_dir = tmp_dir / "out"
            output_dir.mkdir(parents=True, exist_ok=True)

            api_key = str(job.api_key or "")
            job.api_key = None
            cfg = dict(job.settings or {})
            mode = job.mode

            _apply_runtime_config(cfg, api_key=api_key)
            os.environ["DISABLE_TQDM"] = "1"

            await _emit(job, {"type": "log", "message": f"Mode: {mode}"})
            await _emit(job, {"type": "log", "message": f"Provider: {te.PROVIDER}"})

            offline = bool(cfg.get("offline", False))
            if te.TRANSLATE_ENABLED and te.provider_key_missing() and not offline:
                offline = True
                await _emit(job, {"type": "log", "message": "Missing API key → offline"})

            # Prepare input file for public sector mode
            input_file = ""
            if mode == "public_sector" and job.uploaded_bytes:
                stem = Path(job.input_name).stem or "input"
                safe_name = f"{stem}{job.input_ext}"
                input_path = tmp_dir / safe_name
                input_path.write_bytes(job.uploaded_bytes)
                input_file = str(input_path)

            job.uploaded_bytes = None

            def _run():
                return converter.process(
                    mode=mode,
                    input_file=input_file,
                    offline=offline,
                    output_dir=str(output_dir),
                )

            loop = asyncio.get_running_loop()
            output_path = await loop.run_in_executor(None, _run)
            if not output_path:
                raise RuntimeError("No output CSV produced")

            job.output_path = str(output_path)
            job.status = "done"
            await _emit(job, {"type": "status", "status": job.status})
            await _emit(job, {"type": "result", "download_url": f"/api/jobs/{job.id}/download"})

        except Exception as e:
            job.status = "error"
            job.error = str(e)
            await _emit(job, {"type": "status", "status": job.status})
            await _emit(job, {"type": "error", "message": job.error})

        finally:
            await _emit(job, {"type": "done"})
            _job_queue.task_done()


@app.on_event("startup")
async def _startup():
    global _worker_started
    if _worker_started:
        return
    _worker_started = True
    asyncio.create_task(_worker_loop())


@app.get("/", response_class=HTMLResponse)
async def index():
    path = STATIC_DIR / "index.html"
    return HTMLResponse(path.read_text(encoding="utf-8"))


@app.post("/api/jobs")
async def create_job(
    file: Optional[UploadFile] = File(None),
    settings_json: str = Form("{}"),
    api_key: str = Form(""),
):
    now = time.time()
    _cleanup_old_jobs(now)

    if len(_jobs) >= MAX_JOBS:
        raise HTTPException(status_code=429, detail="Too many jobs")
    if _job_queue.qsize() >= MAX_QUEUE:
        raise HTTPException(status_code=429, detail="Queue full")

    try:
        settings = json.loads(settings_json or "{}")
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid settings JSON")

    mode = (settings.get("mode") or "commercial").lower()
    if mode not in ("commercial", "public_sector"):
        raise HTTPException(status_code=400, detail="Invalid mode")

    content = None
    filename = "built-in"
    ext = ""

    if file and file.filename:
        content = await file.read()
        if content:
            if len(content) > MAX_UPLOAD_BYTES:
                raise HTTPException(status_code=413, detail=f"File too large (max {MAX_UPLOAD_MB}MB)")
            _, ext = _detect_input_kind(content)
            filename = Path(file.filename).name

    # For commercial mode, file upload is optional
    if mode == "public_sector" and not content:
        raise HTTPException(status_code=400, detail="Public sector mode requires a file upload")

    job_id = uuid4().hex
    events = asyncio.Queue(maxsize=500)

    job = JobState(
        id=job_id,
        status="queued",
        created_at=now,
        input_name=filename,
        settings=settings,
        input_ext=ext,
        mode=mode,
        uploaded_bytes=content,
        events=events,
        api_key=api_key,
    )
    _jobs[job_id] = job
    await _job_queue.put(job_id)
    await _emit(job, {"type": "status", "status": job.status})

    return {
        "id": job.id,
        "status": job.status,
        "mode": mode,
        "events_url": f"/api/jobs/{job.id}/events",
        "download_url": f"/api/jobs/{job.id}/download",
        "input": job.input_name,
        "config": _safe_config(job.settings or {}),
    }


@app.get("/api/jobs/{job_id}")
async def get_job(job_id: str):
    job = _jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return {
        "id": job.id,
        "status": job.status,
        "mode": job.mode,
        "input": job.input_name,
        "error": job.error,
        "download_url": f"/api/jobs/{job.id}/download" if job.output_path else None,
    }


@app.get("/api/jobs/{job_id}/events")
async def job_events(job_id: str):
    job = _jobs.get(job_id)
    if not job or not job.events:
        raise HTTPException(status_code=404, detail="Job not found")

    async def gen():
        yield _sse_pack({"type": "hello", "job": job.id})
        while True:
            event = await job.events.get()
            yield _sse_pack(event)
            if event.get("type") == "done":
                break

    return StreamingResponse(gen(), media_type="text/event-stream")


@app.get("/api/jobs/{job_id}/download")
async def download(job_id: str):
    job = _jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.status != "done" or not job.output_path:
        raise HTTPException(status_code=409, detail="Job not finished")
    return FileResponse(
        path=job.output_path,
        filename=Path(job.output_path).name,
        media_type="text/csv",
    )
