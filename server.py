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
    m = re.search(
        r'([^.]{10,240}(?:суд.{0,60}указал|оценив доказательства|приш[её]л к выводу)[^.]{0,240}\.)',
        text,
        re.I | re.S,
    )
    s = m.group(1) if m else ""
    return " ".join(s.split()[:max_words])

def norm_candidates(text):
    pats = [
        r"ст\.\s?54\.1\s*НК", r"п\.?\s?14\s*ст\.?\s?101\s*НК",
        r"ст\.\s?169\s*НК", r"ст\.\s?171\s*НК", r"ст\.\s?172\s*НК"
    ]
    found = set()
    for p in pats:
        for m in re.finditer(p, text, re.I):
            norm = safe(m.group()).lower()
            found.add(norm)
    return sorted(found)
