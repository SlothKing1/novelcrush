from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uuid, os, asyncio, json
from datetime import datetime
from scraper import NovelScraper, search_novels
from epub_builder import build_epub

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

NOVELCRUSH_DIR = "/data/data/com.termux/files/home/novelcrush"
LIBRARY_FILE = f"{NOVELCRUSH_DIR}/library.json"

jobs = {}
download_queue = []
queue_processing = False

# ---- LIBRARY HELPERS ----

def load_library():
    try:
        if os.path.exists(LIBRARY_FILE):
            with open(LIBRARY_FILE, "r") as f:
                return json.load(f)
    except:
        pass
    return []

def save_library(data):
    try:
        with open(LIBRARY_FILE, "w") as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        print(f"Library save failed: {e}")

def upsert_library(novel_url, title, cover_url, author, source, last_chapter, total_chapters, filename, filepath):
    lib = load_library()
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    entry = next((e for e in lib if e["url"] == novel_url), None)
    if entry:
        entry["last_chapter"] = last_chapter
        entry["total_chapters_at_download"] = total_chapters
        entry["last_downloaded"] = now
        entry["filename"] = filename
        entry["filepath"] = filepath
        if cover_url:
            entry["cover_url"] = cover_url
    else:
        lib.append({
            "id": str(uuid.uuid4()),
            "url": novel_url,
            "title": title,
            "cover_url": cover_url,
            "author": author,
            "source": source,
            "last_chapter": last_chapter,
            "total_chapters_at_download": total_chapters,
            "last_downloaded": now,
            "filename": filename,
            "filepath": filepath,
            "total_chapters_now": total_chapters
        })
    save_library(lib)

# ---- MODELS ----

class CrawlRequest(BaseModel):
    url: str
    start_chapter: int = 1
    end_chapter: int = None
    clean_titles: bool = False

class QueueRequest(BaseModel):
    url: str
    start_chapter: int = 1
    end_chapter: int = None
    clean_titles: bool = False

class LibraryDeleteRequest(BaseModel):
    id: str
    delete_file: bool = False

# ---- PAGES ----

@app.get("/", response_class=HTMLResponse)
def index():
    return open(f"{NOVELCRUSH_DIR}/index.html").read()

# ---- NOVEL INFO ----

@app.get("/api/novel/info")
async def novel_info(url: str):
    try:
        scraper = NovelScraper(url)
        info = await scraper.get_info()
        await scraper.close()
        return info
    except Exception as e:
        raise HTTPException(400, str(e))

# ---- SEARCH ----

@app.get("/api/search")
async def search(q: str):
    try:
        results = await search_novels(q)
        return {"results": results}
    except Exception as e:
        raise HTTPException(400, str(e))

# ---- DOWNLOAD ----

@app.post("/api/crawl")
async def start_crawl(req: CrawlRequest, bg: BackgroundTasks):
    job_id = str(uuid.uuid4())
    jobs[job_id] = {"status": "pending", "progress": 0, "total": 0, "message": "Starting...", "filepath": None, "filename": "", "novel_title": ""}
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
    return FileResponse(j["filepath"], media_type="application/epub+zip", filename=j["filename"])

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
        filepath = f"{NOVELCRUSH_DIR}/{job_id}_{filename}"
        build_epub(title, chapter_contents, filepath, info.get("cover_url"), info.get("author", "Unknown"), req.clean_titles)
        # Save to library
        upsert_library(
            novel_url=scraper.url,
            title=title,
            cover_url=info.get("cover_url"),
            author=info.get("author", "Unknown"),
            source=info.get("source", ""),
            last_chapter=req.end_chapter or len(chapters),
            total_chapters=len(chapters),
            filename=filename,
            filepath=filepath
        )
        jobs[job_id]["status"] = "done"
        jobs[job_id]["filepath"] = filepath
        jobs[job_id]["filename"] = filename
        jobs[job_id]["message"] = "Done!"
    except Exception as e:
        jobs[job_id]["status"] = "error"
        jobs[job_id]["message"] = str(e)

# ---- LIBRARY ----

@app.get("/api/library")
def get_library():
    return {"library": load_library()}

@app.post("/api/library/delete")
def delete_library_entry(req: LibraryDeleteRequest):
    lib = load_library()
    entry = next((e for e in lib if e["id"] == req.id), None)
    if not entry:
        raise HTTPException(404, "Not found")
    if req.delete_file and entry.get("filepath") and os.path.exists(entry["filepath"]):
        try:
            os.remove(entry["filepath"])
        except:
            pass
    lib = [e for e in lib if e["id"] != req.id]
    save_library(lib)
    return {"ok": True}

@app.get("/api/library/check-updates")
async def check_updates():
    """Check all library novels for new chapters."""
    lib = load_library()
    updates = []
    for entry in lib:
        try:
            scraper = NovelScraper(entry["url"])
            total = await scraper.get_total_chapters()
            await scraper.close()
            new_chapters = total - entry.get("last_chapter", 0)
            if new_chapters > 0:
                updates.append({
                    "id": entry["id"],
                    "title": entry["title"],
                    "new_chapters": new_chapters,
                    "total": total,
                    "last_chapter": entry.get("last_chapter", 0)
                })
            # Update total in library
            entry["total_chapters_now"] = total
        except:
            pass
    save_library(lib)
    return {"updates": updates}

# ---- QUEUE ----

@app.get("/api/queue")
def get_queue():
    return {"queue": download_queue}

@app.post("/api/queue/add")
async def add_to_queue(req: QueueRequest):
    item_id = str(uuid.uuid4())
    # Get novel info for display
    try:
        scraper = NovelScraper(req.url)
        info = await scraper.get_info()
        await scraper.close()
        title = info["title"]
        cover_url = info.get("cover_url")
        total = info["total_chapters"]
    except:
        title = req.url
        cover_url = None
        total = 0

    item = {
        "id": item_id,
        "url": req.url,
        "title": title,
        "cover_url": cover_url,
        "total_chapters": total,
        "start_chapter": req.start_chapter,
        "end_chapter": req.end_chapter or total,
        "clean_titles": req.clean_titles,
        "status": "queued",
        "progress": 0,
        "job_id": None
    }
    download_queue.append(item)
    asyncio.create_task(process_queue())
    return {"id": item_id, "title": title}

@app.delete("/api/queue/{item_id}")
def remove_from_queue(item_id: str):
    global download_queue
    download_queue = [i for i in download_queue if i["id"] != item_id]
    return {"ok": True}

async def process_queue():
    global queue_processing
    if queue_processing:
        return
    queue_processing = True
    try:
        while True:
            pending = [i for i in download_queue if i["status"] == "queued"]
            if not pending:
                break
            item = pending[0]
            item["status"] = "downloading"
            job_id = str(uuid.uuid4())
            item["job_id"] = job_id
            jobs[job_id] = {"status": "pending", "progress": 0, "total": 0, "message": "Starting...", "filepath": None, "filename": "", "novel_title": ""}
            req = CrawlRequest(url=item["url"], start_chapter=item["start_chapter"], end_chapter=item["end_chapter"], clean_titles=item["clean_titles"])
            await run_crawl(job_id, req)
            job = jobs[job_id]
            item["status"] = job["status"]
            item["progress"] = job["progress"]
            item["filename"] = job.get("filename", "")
            item["job_id"] = job_id
    finally:
        queue_processing = False

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
