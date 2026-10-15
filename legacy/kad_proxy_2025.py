# ---------- app.py ----------
"""
KAD-proxy:   /kad/search   и   /kad/details

• Сначала пытается обращаться к КАД напрямую.
• Если получает 451/403 → повторяет запрос через ScraperAPI (RU-гео)
  c опцией forward_method=true – бесплатный тариф это допускает.
"""
import os, time, json, requests, urllib.parse as up
from fastapi import FastAPI, Query
from fastapi.responses import JSONResponse

app = FastAPI(title="KAD proxy")

KAD_URL = "https://kad.arbitr.ru/Kad/SearchInstances"
HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Content-Type": "application/json;charset=UTF-8",
    "X-Requested-With": "XMLHttpRequest",
}

SCRAPER_KEY = os.getenv("SCRAPER_API")        # добавьте в Render → Env Vars
SCRAPER_URL = "https://api.scraperapi.com/"

# ----------------------------------------------------------------------
def kad_request(payload: dict) -> dict:
    """POST в КАД; если 451/403 – fallback через ScraperAPI (RU)."""
    # 1) прямой запрос
    resp = requests.post(KAD_URL, json=payload, headers=HEADERS, timeout=45)

    if resp.status_code in (451, 403) and SCRAPER_KEY:
        proxy_url = (
            f"{SCRAPER_URL}"
            f"?api_key={SCRAPER_KEY}"
            f"&url={up.quote(KAD_URL, safe='')}"
            f"&country_code=ru"
            f"&forward_method=true"      # пробросить исходный POST
            f"&forward_headers=true"
            f"&render=false"
        )
        resp = requests.post(proxy_url, json=payload, headers=HEADERS, timeout=60)

    resp.raise_for_status()              # 4xx/5xx → исключение
    return resp.json()

# ----------------------------------------------------------------------
@app.get("/kad/search", tags=["KAD"])
def search_kad_cases(
    q: str = Query(..., description="Ключевые слова, статья, ИНН, ФИО"),
    page: int = Query(1, ge=1, description="Номер страницы"),
):
    payload = {
        "Page": page,
        "Count": 20,
        "Text": q,
        "CaseNumber": "",
        "Sides": [],
        "Judges": [],
        "WithVKSInstances": True,
        "WithoutVKSInstances": False,
    }
    raw = kad_request(payload)
    rows = raw.get("Instances", [])
    results = [
        {
            "case":   row.get("CaseNumber"),
            "link":   f"https://kad.arbitr.ru/Card/{row.get('CaseId')}",
            "court":  row.get("CourtName"),
            "date":   row.get("Date"),
        }
        for row in rows
    ]
    return JSONResponse({"results": results})

# ----------------------------------------------------------------------
@app.get("/kad/details", tags=["KAD"])
def get_kad_case_details(
    caseNumber: str = Query(..., description="Номер дела, напр. А40-5001/2022")
):
    return kad_request({"CaseNumber": caseNumber})

# ----------------------------------------------------------------------
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app:app",
        host="0.0.0.0",
        port=int(os.getenv("PORT", 8000)),
        reload=True,
    )
