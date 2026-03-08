from ebooklib import epub
import urllib.request
import re

def clean_chapter_title(title):
    # "Chapter 41 - Chapter 41: Chen Yuan" -> "Chapter 41: Chen Yuan"
    cleaned = re.sub(r'^(Chapter\s+\d+)\s*[-–]\s*\1[:\s]*', r'\1: ', title, flags=re.IGNORECASE)
    # "C641 - Chapter 641: Title" -> "Chapter 641: Title"
    cleaned = re.sub(r'^C(\d+)\s*[-–]\s*Chapter\s+\1[:\s]*', r'Chapter \1: ', cleaned, flags=re.IGNORECASE)
    # "641 - Chapter 641: Title" -> "Chapter 641: Title"
    cleaned = re.sub(r'^\d+\s*[-–]\s*(Chapter\s+\d+)', r'\1', cleaned, flags=re.IGNORECASE)
    return cleaned.strip()

def build_epub(title, chapters, output_path, cover_url=None, author="Unknown", clean_titles=False):
    book = epub.EpubBook()
    book.set_title(title)
    book.set_language("en")
    book.add_author(author)

    # Add cover image
    if cover_url:
        try:
            cover_data = urllib.request.urlopen(cover_url, timeout=10).read()
            ext = cover_url.split(".")[-1].split("?")[0].lower()
            if ext not in ["jpg", "jpeg", "png", "gif", "webp"]:
                ext = "jpg"
            media_type = "image/jpeg" if ext in ["jpg", "jpeg"] else f"image/{ext}"
            book.set_cover(f"cover.{ext}", cover_data)
        except Exception as e:
            print(f"Cover download failed: {e}")

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
        c = epub.EpubHtml(title=ch_title, file_name=f"chapter_{i+1}.xhtml", lang="en")

        # Build paragraphs
        paragraphs = ""
        for para in ch["content"].split("\n\n"):
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
