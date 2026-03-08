from ebooklib import epub
import re

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.google.com/",
}

def download_cover(url):
    """Download cover image with full browser headers so any site allows it."""
    try:
        import urllib.request
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=15) as r:
            return r.read()
    except Exception as e:
        print(f"Cover download failed: {e}")
        return None

def clean_chapter_title(title):
    # "Chapter 41 - Chapter 41: Chen Yuan" -> "Chapter 41: Chen Yuan"
    cleaned = re.sub(r'^(Chapter\s+\d+)\s*[-–]\s*\1[:\s]*', r'\1: ', title, flags=re.IGNORECASE)
    # "C641 - Chapter 641: Title" -> "Chapter 641: Title"
    cleaned = re.sub(r'^C(\d+)\s*[-–]\s*Chapter\s+\1[:\s]*', r'Chapter \1: ', cleaned, flags=re.IGNORECASE)
    # "641 - Chapter 641: Title" -> "Chapter 641: Title"
    cleaned = re.sub(r'^\d+\s*[-–]\s*(Chapter\s+\d+)', r'\1', cleaned, flags=re.IGNORECASE)
    return cleaned.strip()

def remove_duplicate_first_para(title, content):
    """Remove first paragraph if it duplicates the chapter title."""
    paras = [p.strip() for p in content.split("\n\n") if p.strip()]
    if not paras:
        return content
    first = paras[0].strip()
    if first.lower() == title.lower() or first.lower() == clean_chapter_title(title).lower():
        paras = paras[1:]
    return "\n\n".join(paras)

def build_epub(title, chapters, output_path, cover_url=None, author="Unknown", clean_titles=False):
    book = epub.EpubBook()
    book.set_title(title)
    book.set_language("en")
    book.add_author(author)

    # Add cover image using browser headers
    if cover_url:
        cover_data = download_cover(cover_url)
        if cover_data:
            try:
                ext = cover_url.split(".")[-1].split("?")[0].lower()
                if ext not in ["jpg", "jpeg", "png", "gif", "webp"]:
                    ext = "jpg"
                book.set_cover(f"cover.{ext}", cover_data)
            except Exception as e:
                print(f"Cover set failed: {e}")

    # CSS styling
    style = """
body {
    font-family: Georgia, serif;
    margin: 2em;
    line-height: 1.8;
    color: #1a1a1a;
}
h1 {
    font-size: 1.8em;
    text-align: center;
    margin-bottom: 1.5em;
    color: #333;
}
p {
    margin-bottom: 1em;
    text-indent: 1.5em;
    text-align: justify;
}
"""
    css = epub.EpubItem(uid="style", file_name="style/style.css", media_type="text/css", content=style.encode("utf-8"))
    book.add_item(css)

    epub_chapters = []
    for i, ch in enumerate(chapters):
        ch_title = clean_chapter_title(ch["title"]) if clean_titles else ch["title"]
        content = remove_duplicate_first_para(ch_title, ch["content"])

        c = epub.EpubHtml(title=ch_title, file_name=f"chapter_{i+1}.xhtml", lang="en")

        paragraphs = ""
        for para in content.split("\n\n"):
            para = para.strip()
            if para:
                paragraphs += f"<p>{para}</p>\n"

        c.content = f"""<?xml version='1.0' encoding='utf-8'?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml">
<head>
    <title>{ch_title}</title>
    <link rel="stylesheet" type="text/css" href="../style/style.css"/>
</head>
<body>
    <h1>{ch_title}</h1>
    {paragraphs}
</body>
</html>""".encode("utf-8")

        c.add_item(css)
        book.add_item(c)
        epub_chapters.append(c)

    book.toc = tuple(epub_chapters)
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())
    book.spine = ["nav"] + epub_chapters

    epub.write_epub(output_path, book)
