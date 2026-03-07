import aiohttp, re
from bs4 import BeautifulSoup
from urllib.parse import urlparse, urljoin

SOURCES = {
    "royalroad.com": {"title": "h1.font-white", "cover": ".cover-art-container img", "author": "span[property='name']", "chapter_content": ".chapter-content"},
    "novelfull.com": {"title": "h3.title", "cover": ".book img", "author": "div.info a", "chapter_content": "div#chapter-content"},
    "lightnovelpub.com": {"title": "h1.novel-title", "cover": ".novel-cover img", "author": ".author span", "chapter_content": ".chapter-content"},
    "freewebnovel.com": {"title": "h1.title", "cover": ".pic img", "author": ".author span", "chapter_content": ".txt"},
    "novelbin.com": {"title": "h3.title", "cover": ".book img", "author": "div.info a", "chapter_content": "div#chr-content"},
    "mtlnovel.com": {"title": "h1.entry-title", "cover": ".novel-cover img", "author": ".novel-author", "chapter_content": ".post-page-numbers"},
}

HEADERS = {"User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1"}

def get_domain(url):
    d = urlparse(url).netloc.lower()
    return d[4:] if d.startswith("www.") else d

class NovelScraper:
    def __init__(self, url):
        self.url = url
        self.domain = get_domain(url)
        self.cfg = next((v for k, v in SOURCES.items() if k in self.domain), None)
        self._session = None

    async def _sess(self):
        if not self._session:
            self._session = aiohttp.ClientSession(headers=HEADERS)
        return self._session

    async def fetch(self, url):
        s = await self._sess()
        async with s.get(url, timeout=aiohttp.ClientTimeout(total=30)) as r:
            r.raise_for_status()
            return BeautifulSoup(await r.text(), "html.parser")

    async def get_info(self):
        soup = await self.fetch(self.url)
        title = self._text(soup, self.cfg["title"] if self.cfg else None) or self._smart_title(soup)
        cover = self._attr(soup, self.cfg["cover"] if self.cfg else None, "src") or self._smart_cover(soup)
        author = self._text(soup, self.cfg["author"] if self.cfg else None) or self._smart_author(soup)
        chapters = await self._get_chapters(soup)
        return {"title": title or "Unknown Novel", "cover_url": cover, "author": author or "Unknown", "chapters": chapters, "total_chapters": len(chapters), "source": self.domain}

    async def _get_chapters(self, soup):
        if "royalroad.com" in self.domain:
            return [{"title": a.get_text(strip=True), "url": urljoin(self.url, a["href"])} for row in soup.select("table#chapters tbody tr") for a in [row.select_one("td a")] if a]
        return await self._smart_chapters(soup)

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
