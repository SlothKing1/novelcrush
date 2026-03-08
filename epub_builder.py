from ebooklib import epub
import aiohttp
import asyncio

def build_epub(title, chapters, output_path, cover_url=None, author="Unknown"):
    book = epub.EpubBook()
    book.set_title(title)
    book.set_language("en")
    book.add_author(author)

    # Add cover image
    if cover_url:
        try:
            import urllib.request
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
    css = epub.EpubItem(uid="style", file_name="style/style.css", media_type="text/css", content=style)
    book.add_item(css)

    epub_chapters = []
    for i, ch in enumerate(chapters):
        c = epub.EpubHtml(title=ch["title"], file_name=f"chapter_{i+1}.xhtml", lang="en")

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
    <title>{ch['title']}</title>
    <link rel="stylesheet" type="text/css" href="../style/style.css"/>
</head>
<body>
    <h1>{ch['title']}</h1>
    {paragraphs}
</body>
</html>"""
        c.add_item(css)
        book.add_item(c)
        epub_chapters.append(c)

    book.toc = tuple(epub_chapters)
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())
    book.spine = ["nav"] + epub_chapters

    epub.write_epub(output_path, book)
