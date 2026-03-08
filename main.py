from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uuid, os, asyncio
from scraper import NovelScraper
from epub_builder import build_epub

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

jobs = {}

class CrawlRequest(BaseModel):
    url: str
    start_chapter: int = 1
    end_chapter: int = None

@app.get("/", response_class=HTMLResponse)
def index():
    return open("index.html").read()

@app.get("/api/novel/info")
async def novel_info(url: str):
    try:
        scraper = NovelScraper(url)
        info = await scraper.get_info()
        await scraper.close()
        return info
    except Exception as e:
        raise HTTPException(400, str(e))

@app.post("/api/crawl")
async def start_crawl(req: CrawlRequest, bg: BackgroundTasks):
    job_id = str(uuid.uuid4())
    jobs[job_id] = {"status": "pending", "progress": 0, "total": 0, "message": "Starting...", "filepath": None, "novel_title": ""}
    bg.add_task(run_crawl, job_id, req)
    return {"job_id": job_id}

@app.get("/api/job/{job_id}")
def job_status(job_id: str):
    if job_id not in jobs:
        raise HTTPException(404, "Not found")
    return jobs[job_id]

@app.get("/api/download/{job_id}")
def download(job_id: str):
    if job_id not in jobs:
        raise HTTPException(404, "Not found")
    j = jobs[job_id]
    if j["status"] != "done" or not j["filepath"] or not os.path.exists(j["filepath"]):
        raise HTTPException(400, "File not ready")
    return FileResponse(j["filepath"], media_type="application/epub+zip", filename=os.path.basename(j["filepath"]))

async def run_crawl(job_id, req):
    try:
        jobs[job_id]["status"] = "running"
        jobs[job_id]["message"] = "Fetching novel info..."
        scraper = NovelScraper(req.url)
        info = await scraper.get_info()
        title = info["title"]
        chapters = info["chapters"]
        start = max(0, (req.start_chapter or 1) - 1)
        end = min(len(chapters), req.end_chapter or len(chapters))
        selected = chapters[start:end]
        jobs[job_id]["total"] = len(selected)
        jobs[job_id]["novel_title"] = title
        chapter_contents = []
        for i, ch in enumerate(selected):
            jobs[job_id]["progress"] = i + 1
            jobs[job_id]["message"] = f"Downloading chapter {start + i + 1} of {end}..."
            content = await scraper.get_chapter(ch["url"])
            chapter_contents.append({"title": ch["title"], "content": content, "number": start + i + 1})
        await scraper.close()
        jobs[job_id]["message"] = "Building EPUB..."
        safe_title = "".join(c for c in title if c.isalnum() or c in " .-_").strip()
        filename = f"{safe_title} Ch.{req.start_chapter or 1}-{req.end_chapter or len(chapters)}.epub"
        filepath = f"/tmp/{job_id}_{filename}"
        build_epub(title, chapter_contents, filepath, info.get("cover_url"), info.get("author", "Unknown"))
        jobs[job_id]["status"] = "done"
        jobs[job_id]["filepath"] = filepath
        jobs[job_id]["message"] = "Done!"
    except Exception as e:
        jobs[job_id]["status"] = "error"
        jobs[job_id]["message"] = str(e)
        if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
