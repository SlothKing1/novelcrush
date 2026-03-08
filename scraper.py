import aiohttp, re, asyncio
from bs4 import BeautifulSoup
from urllib.parse import urlparse, urljoin

SOURCES = {
    "royalroad.com": {"title": "h1.font-white", "cover": ".cover-art-container img", "author": "span[property='name']", "chapter_content": ".chapter-content"},
    "novelfull.com": {"title": "h3.title", "cover": ".book img", "author": "div.info a", "chapter_content": "div#chapter-content"},
    "lightnovelpub.com": {"title": "h1.novel-title", "cover": ".novel-cover img", "author": ".author span", "chapter_content": ".chapter-content"},
    "freewebnovel.com": {"title": "h1.title", "cover": ".pic img", "author": ".author span", "chapter_content": ".txt"},
    "novelbin.com": {"title": "h3.title", "cover": ".book img", "author": "div.info a", "chapter_content": "div#chr-content"},
    "novelbin.me": {"title": "h3.title", "cover": ".book img", "author": "div.info a", "chapter_content": "div#chr-content"},
    "mtlnovel.com": {"title": "h1.entry-title", "cover": ".novel-cover img", "author": ".novel-author", "chapter_content": ".post-page-numbers"},
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "Cache-Control": "max-age=0",
}

def get_domain(url):
    d = urlparse(url).netloc.lower()
    return d[4:] if d.startswith("www.") else d

def _find_last_page(soup):
    """
    Reliably find the last page number from any pagination structure.
    Strategy 1: Look for 'Last' or '>>' link and read page number from its href.
    Strategy 2: Scan ALL pagination hrefs and take the highest page number found.
    Works for any site regardless of how many pages there are.
    """
    last_page = 1

    # Strategy 1: Find explicit "Last" or ">>" button and read from href
    for a in soup.select("ul.pagination li a, .pagination a, nav a"):
        text = a.get_text(strip=True).lower()
        href = a.get("href", "")
        if any(kw in text for kw in ["last", "»", ">>"]):
            m = re.search(r'[?&]page=(\d+)', href)
            if m:
                last_page = max(last_page, int(m.group(1)))

    # Strategy 2: Scan all pagination links for highest page number in href
    for a in soup.select("ul.pagination li a, .pagination a, nav a"):
        href = a.get("href", "")
        m = re.search(r'[?&]page=(\d+)', href)
        if m:
            last_page = max(last_page, int(m.group(1)))

    return last_page

class NovelScraper:
    def __init__(self, url):
        self.url = re.sub(r'[?&]page=\d+', '', url).rstrip("/")
        self.domain = get_domain(url)
        self.cfg = next((v for k, v in SOURCES.items() if k in self.domain), None)
        self._session = None

    async def _sess(self):
        if not self._session:
            connector = aiohttp.TCPConnector(ssl=False)
            self._session = aiohttp.ClientSession(
                headers=HEADERS,
                connector=connector,
                cookie_jar=aiohttp.CookieJar()
            )
        return self._session

    async def fetch(self, url, retries=3):
        s = await self._sess()
        for attempt in range(retries):
            try:
                await asyncio.sleep(0.5 * attempt)
                async with s.get(url, timeout=aiohttp.ClientTimeout(total=30), allow_redirects=True) as r:
                    if r.status == 403:
                        raise Exception(f"Site blocked access (403). Try freewebnovel.com or royalroad.com instead.")
                    if r.status == 404:
                        raise Exception(f"Page not found (404). Check the URL is correct.")
                    r.raise_for_status()
                    html = await r.text()
                    return BeautifulSoup(html, "html.parser")
            except Exception as e:
                if attempt == retries - 1:
                    raise
                await asyncio.sleep(1)

    async def get_info(self):
        soup = await self.fetch(self.url)
        title = self._text(soup, self.cfg["title"] if self.cfg else None) or self._smart_title(soup)
        cover = self._attr(soup, self.cfg["cover"] if self.cfg else None, "src") or self._smart_cover(soup)
        author = self._text(soup, self.cfg["author"] if self.cfg else None) or self._smart_author(soup)
        chapters = await self._get_chapters(soup)
        return {
            "title": title or "Unknown Novel",
            "cover_url": cover,
            "author": author or "Unknown",
            "chapters": chapters,
            "total_chapters": len(chapters),
            "source": self.domain
        }

    async def _get_chapters(self, soup):
        if "royalroad.com" in self.domain:
            chapters = [{"title": a.get_text(strip=True), "url": urljoin(self.url, a["href"])}
                    for row in soup.select("table#chapters tbody tr")
                    for a in [row.select_one("td a")] if a]
            return chapters
        if "novelfull.com" in self.domain or "novelbin" in self.domain:
            return await self._paginated_chapters(soup)
        return await self._smart_chapters(soup)

    async def _paginated_chapters(self, soup):
        chapters = self._chapter_links(soup)

        last_page = _find_last_page(soup)
        print(f"[scraper] Total pages: {last_page}")

        base = re.sub(r'[?&]page=\d+', '', self.url).rstrip("/")
        for page in range(2, last_page + 1):
            try:
                s2 = await self.fetch(f"{base}?page={page}")
                chapters += self._chapter_links(s2)
            except:
                pass

        # Remove duplicates preserving order
        seen, out = set(), []
        for ch in chapters:
            if ch["url"] not in seen:
                seen.add(ch["url"])
                out.append(ch)

        # Sort by first number found in title
        def get_chapter_num(ch):
            nums = re.findall(r'\d+', ch["title"])
            return int(nums[0]) if nums else 0

        out.sort(key=get_chapter_num)
        return out

    async def _smart_chapters(self, soup):
        links = self._chapter_links(soup)
        if len(links) < 3:
            for suffix in ["/chapters", "/chapter-list", "?tab=chapters"]:
                try:
                    s2 = await self.fetch(self.url.rstrip("/") + suffix)
                    links = self._chapter_links(s2)
                    if links: break
                except: pass
        seen, out = set(), []
        for ch in links:
            if ch["url"] not in seen:
                seen.add(ch["url"])
                out.append(ch)

        def get_chapter_num(ch):
            nums = re.findall(r'\d+', ch["title"])
            return int(nums[0]) if nums else 0

        out.sort(key=get_chapter_num)
        return out

    def _chapter_links(self, soup):
        out = []
        for a in soup.find_all("a", href=True):
            t, h = a.get_text(strip=True), a["href"]
            if re.search(r"chapter|ch\.?\s*\d|chap", h + t, re.I) and t:
                out.append({"title": t, "url": urljoin(self.url, h)})
        return out

    async def get_chapter(self, url):
        soup = await self.fetch(url)
        if self.cfg and self.cfg.get("chapter_content"):
            el = soup.select_one(self.cfg["chapter_content"])
            if el: return self._clean(el)
        return self._smart_content(soup)

    def _smart_content(self, soup):
        for tag in soup.select("nav,header,footer,.ads,script,style,.comments"): tag.decompose()
        candidates = [(len(el.get_text()), el) for el in soup.find_all(["div","article","section"]) if len(el.get_text(strip=True)) > 500]
        if candidates:
            return self._clean(sorted(candidates, reverse=True)[0][1])
        return soup.get_text()

    def _clean(self, el):
        for t in el.select("script,style,.ads,a[href*='patreon'],a[href*='discord']"): t.decompose()
        ps = el.find_all("p")
        if ps: return "\n\n".join(p.get_text(strip=True) for p in ps if p.get_text(strip=True))
        return el.get_text(separator="\n\n", strip=True)

    def _smart_title(self, soup):
        for sel in ["h1",".novel-title",".title","[class*='title']"]:
            el = soup.select_one(sel)
            if el and len(el.get_text(strip=True)) > 2: return el.get_text(strip=True)
        return soup.title.string if soup.title else "Unknown"

    def _smart_cover(self, soup):
        for sel in [".cover img",".book-cover img",".novel-cover img","img[class*='cover']"]:
            el = soup.select_one(sel)
            if el and el.get("src"): return urljoin(self.url, el["src"])
        return None

    def _smart_author(self, soup):
        for sel in [".author","[class*='author']","span[itemprop='author']"]:
            el = soup.select_one(sel)
            if el: return el.get_text(strip=True)
        return None

    def _text(self, soup, sel):
        if not sel: return ""
        el = soup.select_one(sel)
        return el.get_text(strip=True) if el else ""

    def _attr(self, soup, sel, attr):
        if not sel: return ""
        el = soup.select_one(sel)
        if el:
            v = el.get(attr, "")
            return urljoin(self.url, v) if v else ""
        return ""

    async def close(self):
        if self._session: await self._session.close()
