from ebooklib import epub
import uuid, urllib.request

def build_epub(title, chapters, output_path, cover_url=None, author="Unknown"):
    book = epub.EpubBook()
    book.set_identifier(str(uuid.uuid4()))
    book.set_title(title)
    book.set_language("en")
    book.add_author(author)

    if cover_url:
        try:
            data = urllib.request.urlopen(cover_url, timeout=10).read()
            ext = cover_url.split(".")[-1].split("?")[0].lower()
            ext = "jpeg" if ext == "jpg" else ext
            book.set_cover(f"cover.{ext}", data)
        except: pass

    css = epub.EpubItem(uid="style", file_name="style.css", media_type="text/css", content="""
        body { font-family: Georgia, serif; font-size: 1em; line-height: 1.8; margin: 1em 2em; color: #1a1a1a; }
        h2 { font-size: 1.2em; border-bottom: 1px solid #ddd; padding-bottom: 0.3em; margin-bottom: 1em; }
        p { margin: 0.7em 0; text-indent: 1.5em; } p:first-of-type { text-indent: 0; }
    """)
    book.add_item(css)

    epub_chs, toc = [], []
    for ch in chapters:
        fid = f"chapter_{ch['number']}"
        html = "".join(f"<p>{p}</p>" for p in ch["content"].split("\n\n") if p.strip())
        body = f"""<?xml version='1.0' encoding='utf-8'?>
<!DOCTYPE html><html xmlns="http://www.w3.org/1999/xhtml">
<head><title>{ch['title']}</title><link rel="stylesheet" type="text/css" href="style.css"/></head>
<body><h2>{ch['title']}</h2>{html}</body></html>"""
        ec = epub.EpubHtml(title=ch["title"], file_name=f"{fid}.xhtml", lang="en", uid=fid)
        ec.content = body
        ec.add_item(css)
        book.add_item(ec)
        epub_chs.append(ec)
        toc.append(epub.Link(f"{fid}.xhtml", ch["title"], fid))

    book.toc = toc
    book.spine = ["nav"] + epub_chs
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())
    epub.write_epub(output_path, book)
    return output_path
