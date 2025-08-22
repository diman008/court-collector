from fastapi import FastAPI, UploadFile, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel
from typing import List
import re, csv, uuid, asyncio, yaml
from pathlib import Path
from playwright.async_api import async_playwright

app = FastAPI(title="Court Collector", version="1.1.0")

DATA = Path("data"); DATA.mkdir(exist_ok=True)
JOBS = {}  # job_id -> {"status": "...", "links": [], "csv": Path|None, "log": []}

class CollectConfig(BaseModel):
    queries: List[str]
    year_from: int = 2017
    instances: List[str] = ["апелляция","кассация","ВС"]
    max_links_per_query: int = 30
    pause_sec: int = 6

def safe(s): 
    return re.sub(r"\s+"," ", s or "").strip()

def pick_quote(text, max_words=25):
    m = re.search(r'([^.]{10,240}(?:суд.{0,60}указал|оценив доказательства|приш[её]л к выводу)[^.]{0,240}\.)', text, re.I|re.S)
    s = (m.group(1) if m else "")
    return " ".join(s.split()[:max_words])

def norm_candidates(text: str) -> List[str]:
    """Return normative citation candidates found in *text*."""
    pats = [
        r"ст\.\s?54\.1\s*НК", r"п\.?\s?14\s*ст\.?\s?101\s*НК",
        r"ст\.\s?169\s*НК", r"ст\.\s?171\s*НК", r"ст\.\s?172\s*НК",
    ]
    found: List[str] = []
    for p in pats:
        for m in re.finditer(p, text, re.I):
<<<<<<< ours
            found.append(m.group())
    return found


async def run_job(job_id: str, config: CollectConfig) -> None:
    job = JOBS[job_id]
    job["log"].append("started")
    for q in config.queries:
        await asyncio.sleep(0)
        link = f"https://example.com/search?q={q}"
        job["links"].append(link)
        job["log"].append(f"processed {q}")
    csv_path = DATA / f"{job_id}.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["link"])
        for link in job["links"]:
            writer.writerow([link])
    job["csv"] = csv_path
    job["status"] = "finished"
    job["log"].append("finished")


@app.post("/start")
async def start_job(cfg: CollectConfig):
    job_id = str(uuid.uuid4())
    JOBS[job_id] = {"status": "running", "links": [], "csv": None, "log": []}
    asyncio.create_task(run_job(job_id, cfg))
    return {"job_id": job_id, "status": JOBS[job_id]["status"]}


@app.get("/status/{job_id}")
async def get_status(job_id: str):
    job = JOBS.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="job not found")
    return {
        "job_id": job_id,
        "status": job["status"],
        "links": job["links"],
        "csv": str(job["csv"]) if job["csv"] else None,
        "log": job["log"],
    }


@app.get("/download/{job_id}")
async def download_csv(job_id: str):
    job = JOBS.get(job_id)
    if not job or not job.get("csv"):
        raise HTTPException(status_code=404, detail="CSV not ready")
    return FileResponse(job["csv"], media_type="text/csv", filename=f"{job_id}.csv")
=======
            found.append(m.group(0))
    return found
>>>>>>> theirs
