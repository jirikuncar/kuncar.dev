"""Write docs/sitemap.xml from the HTML pages in docs/.

A staged page gets today's date as lastmod; any other page keeps the date of
its last commit.
"""

import datetime
import subprocess
from pathlib import Path
from xml.sax.saxutils import escape

ROOT = "https://kuncar.dev/"
DOCS = Path(__file__).resolve().parent.parent / "docs"


def git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=DOCS, capture_output=True, text=True, check=True).stdout.strip()


def lastmod(page: Path, staged: set[str]) -> str:
    if str(page) in staged:
        return datetime.date.today().isoformat()
    return git("log", "-1", "--format=%cs", "--", str(page)) or datetime.date.today().isoformat()


def url(page: Path) -> str:
    path = page.as_posix().removesuffix("index.html")
    return ROOT + path


def main() -> None:
    staged = set(git("diff", "--cached", "--name-only", "--relative", "--", ".").splitlines())
    pages = sorted(p.relative_to(DOCS) for p in DOCS.rglob("*.html"))
    entries = "".join(
        f"  <url>\n    <loc>{escape(url(p))}</loc>\n    <lastmod>{lastmod(p, staged)}</lastmod>\n  </url>\n"
        for p in pages
    )
    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        f"{entries}</urlset>\n"
    )
    path = DOCS / "sitemap.xml"
    if not path.exists() or path.read_text() != xml:
        path.write_text(xml)


if __name__ == "__main__":
    main()
