"""Validate local links and fragments in a built MkDocs site."""

import argparse
import hashlib
import json
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]

def source_hashes():
    paths = [ROOT / "docs/mkdocs.yml", *(ROOT / "docs/docs").rglob("*")]
    return {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(paths) if p.is_file()}


class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids = set()
        self.targets = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if attrs.get("id"):
            self.ids.add(attrs["id"])
        if tag == "a" and attrs.get("name"):
            self.ids.add(attrs["name"])
        key = "src" if tag in {"img", "script"} else "href"
        if tag in {"a", "link", "img", "script"} and attrs.get(key):
            self.targets.append(attrs[key])


def check(root, base_url):
    root = root.resolve()
    base = urlsplit(base_url)
    prefix = base.path.rstrip("/")
    pages = {}
    for path in root.rglob("*.html"):
        parser = Links()
        parser.feed(path.read_text())
        pages[path.resolve()] = parser
    errors, checked, external = [], 0, set()
    for page, parser in pages.items():
        for href in parser.targets:
            url = urlsplit(href)
            if url.scheme and url.scheme not in {"http", "https"}:
                continue
            if url.netloc and url.netloc != base.netloc:
                external.add(href)
                continue
            path = unquote(url.path)
            if path.startswith("/"):
                if prefix and path != prefix and not path.startswith(prefix + "/"):
                    external.add(href)
                    continue
                target = root / path[len(prefix):].lstrip("/")
            else:
                target = page.parent / path if path else page
            target = target.resolve()
            if target.is_dir():
                target = target / "index.html"
            checked += 1
            error = None
            if not target.is_relative_to(root) or not target.exists():
                error = "missing local target"
            elif url.fragment and target in pages and unquote(url.fragment) not in pages[target].ids:
                error = "missing fragment"
            if error:
                errors.append({"page": str(page.relative_to(root)), "link": href, "error": error})
    return {"schema_version": 1, "pass": not errors, "html_pages": len(pages),
            "local_links_checked": checked, "errors": errors,
            "external_links_not_fetched": len(external),
            "scope": "Rendered href/src targets and HTML fragments; external sites and CSS url() references are not fetched"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--site", type=Path, required=True)
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = check(args.site, args.base_url)
    assert result["html_pages"], "No rendered HTML found"
    result["source_sha256"] = source_hashes()
    result["runner_sha256"] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(f"{result['html_pages']} pages, {result['local_links_checked']} local links/assets, {len(result['errors'])} errors")
    for error in result["errors"]:
        print(error)
    raise SystemExit(not result["pass"])


if __name__ == "__main__":
    main()
