from fastapi import FastAPI, UploadFile, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel
from typing import List
import re, csv, time, uuid, asyncio, yaml
from pathlib import Path
from playwright.async_api import async_playwright

app = FastAPI(title="Court Collector", version="1.0.0")

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

def norm_candidates(text):
    pats = [
        r"ст\.\s?54\.1\s*НК", r"п\.?\s?14\s*ст\.?\s?101\s*НК",
        r"ст\.\s?169\s*НК", r"ст\.\s?171\s*НК", r"ст\.\s?172\s*НК"
    ]
    found = []
    for p in pats:
        for m in re.finditer(p, text, re.I):
            found.append(m.group(0))
    repl = {
        "ст. 54.1 НК": "НК РФ ст.54.1",
        "п.14 ст.101 НК": "НК РФ п.14 ст.101",
        "ст. 169 НК": "НК РФ ст.169",
        "ст. 171 НК": "НК РФ ст.171",
        "ст. 172 НК": "НК РФ ст.172",
    }
    out = []
    for f in sorted(set(found), key=str.lower):
        k = f.replace("\u00A0"," ")
        for a,b in repl.items():
            if a.lower() in k.lower():
                out.append(b)
                break
    return "|".join(sorted(set(out)))

async def collect_links_from_kad(page, query, year_from, instances, max_links, pause, log):
    await page.goto("https://kad.arbitr.ru/", wait_until="domcontentloaded")
    await page.wait_for_timeout(pause*1000)
    # Базовый поиск по строке
    await page.fill("input[placeholder='Поиск по делам']", query)
    await page.keyboard.press("Enter")
    await page.wait_for_load_state("networkidle")
    links = set()
    while len(links) < max_links:
        ahrefs = await page.locator("a").all()
        for a in ahrefs:
            href = await a.get_attribute("href")
            if href and "Card" in href and href.startswith("http"):
                links.add(href)
                if len(links) >= max_links: break
        if len(links) < max_links and await page.locator("text=Следующая").is_visible():
            await page.click("text=Следующая")
            await page.wait_for_load_state("networkidle")
            await page.wait_for_timeout(pause*1000)
        else:
            break
    log.append(f"KAD: '{query}' -> {len(links)} ссылок")
    return list(links)

async def collect_links_from_ras(page, query, year_from, instances, max_links, pause, log):
    await page.goto("https://ras.arbitr.ru/", wait_until="domcontentloaded")
    await page.wait_for_timeout(pause*1000)
    await page.fill("input[type='search']", query)
    await page.keyboard.press("Enter")
    await page.wait_for_load_state("networkidle")
    links = set()
    while len(links) < max_links:
        ahrefs = await page.locator("a").all()
        for a in ahrefs:
            href = await a.get_attribute("href") or ""
            if "/Document" in href or "/Ras" in href:
                if href.startswith("/"): href = "https://ras.arbitr.ru" + href
                links.add(href)
                if len(links) >= max_links: break
        if len(links) < max_links and await page.locator("text=Следующая").is_visible():
            await page.click("text=Следующая")
            await page.wait_for_load_state("networkidle")
            await page.wait_for_timeout(pause*1000)
        else:
            break
    log.append(f"RAS: '{query}' -> {len(links)} ссылок")
    return list(links)

async def grab_visible_text(page, url, pause):
    await page.goto(url, wait_until="networkidle")
    await page.wait_for_timeout(pause*1000)
    try:
        return await page.inner_text("body")
    except:
        return ""

def extract_fields(url, raw_text):
    txt = re.sub(r"\s+"," ", raw_text or "")
    def get(pat):
        m = re.search(pat, txt, re.I|re.S)
        return safe(m.group(1)) if m else ""
    return {
        "system": "АПК",
        "instance": get(r"Инстанция[:\s]*([А-ЯA-Za-zа-я\s\-]{3,40})"),
        "court": get(r"(Арбитражный\s*суд[^\n]{5,120})"),
        "case_number": get(r"(?:Дело|№\s*дела|Дело\s*№)\s*[:№]*\s*([AА]?\d{1,3}-\d+/\d{4}|\w+-\d+/\d{4})"),
        "decision_date": get(r"(?:дата|от)\s*[:\s]*?(\d{2}[.\-]\d{2}[.\-]\d{4})"),
        "outcome": "",
        "region": "",
        "url": url,
        "quote_25w": pick_quote(txt),
        "norms": norm_candidates(txt),
        "source": "visible_text"
    }

async def run_job(job_id: str, cfg: CollectConfig):
    log = JOBS[job_id]["log"]
    JOBS[job_id]["status"] = "collecting-links"
    all_links = set()
    async with async_playwright() as p:
        br = await p.chromium.launch(headless=True)
        page = await br.new_page()
        for q in cfg.queries:
            try:
                kad = await collect_links_from_kad(page, q, cfg.year_from, cfg.instances, cfg.max_links_per_query, cfg.pause_sec, log)
                ras = await collect_links_from_ras(page, q, cfg.year_from, cfg.instances, cfg.max_links_per_query, cfg.pause_sec, log)
                all_links.update(kad); all_links.update(ras)
                await asyncio.sleep(cfg.pause_sec)
            except Exception as e:
                log.append(f"Ошибка сбора ссылок для '{q}': {e}")
        await br.close()
    links_list = sorted(all_links)
    JOBS[job_id]["links"] = links_list
    JOBS[job_id]["status"] = "extracting"

    rows = []
    async with async_playwright() as p:
        br = await p.chromium.launch(headless=True)
        page = await br.new_page()
        for u in links_list:
            try:
                txt = await grab_visible_text(page, u, cfg.pause_sec)
                rows.append(extract_fields(u, txt))
            except Exception as e:
                log.append(f"Ошибка чтения {u}: {e}")
            await asyncio.sleep(1.5)
        await br.close()

    seen, deduped = set(), []
    for r in rows:
        key = "|".join([r.get("system",""), r.get("instance",""), r.get("case_number",""), r.get("decision_date","")])
        if key and key not in seen:
            seen.add(key); deduped.append(r)

    csv_path = DATA / f"{job_id}.csv"
    fields = ["system","instance","court","case_number","decision_date","outcome","region","url","quote_25w","norms","source"]
    with open(csv_path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=fields); w.writeheader(); w.writerows(deduped)
    JOBS[job_id]["csv"] = str(csv_path)
    JOBS[job_id]["status"] = "done"
    log.append(f"Готово: {len(deduped)} записей")

@app.post("/start")
async def start_job(cfg: CollectConfig):
    job_id = uuid.uuid4().hex
    JOBS[job_id] = {"status":"queued", "links":[], "csv":None, "log":[]}
    asyncio.create_task(run_job(job_id, cfg))
    return {"job_id": job_id, "status": "queued"}

@app.get("/status/{job_id}")
def get_status(job_id: str):
    if job_id not in JOBS: raise HTTPException(404, "job not found")
    return {"job_id": job_id, **JOBS[job_id]}

@app.get("/download/{job_id}")
def download(job_id: str):
    if job_id not in JOBS or not JOBS[job_id]["csv"]:
        raise HTTPException(404, "file not ready")
    return FileResponse(JOBS[job_id]["csv"], filename=f"cases_{job_id}.csv", media_type="text/csv")

@app.post("/config/test")
def test_config(file: UploadFile):
    try:
        cfg = yaml.safe_load(file.file.read())
        return JSONResponse({"ok":True, "parsed": cfg})
    except Exception as e:
        return JSONResponse({"ok":False, "error": str(e)}, status_code=400)
