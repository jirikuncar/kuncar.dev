"""Check the Open Graph, Twitter card and JSON-LD metadata of HTML pages, offline.

Open Graph: the basic properties of https://ogp.me/ are present, absolute and agree
with the canonical link. JSON-LD: every @type is a schema.org class and every property
applies to its type, per the vocabulary in vendor/schemaorg-30.1.json, and every
@id reference resolves within the page.
"""

import json
import re
import sys
from html.parser import HTMLParser
from pathlib import Path

VOCAB = json.loads((Path(__file__).parent / "vendor" / "schemaorg-30.1.json").read_text())
CLASSES: dict[str, list[str]] = VOCAB["classes"]
PROPERTIES: dict[str, list[str]] = VOCAB["properties"]

OG_REQUIRED = ("og:title", "og:type", "og:image", "og:url")
OG_TYPES = {"website", "article", "book", "profile", "music.song", "music.album", "video.movie", "video.other"}
TWITTER_CARDS = {"summary", "summary_large_image", "app", "player"}
ABSOLUTE = re.compile(r"^https://\S+$")


class Head(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.meta: dict[str, list[str]] = {}
        self.canonical: str | None = None
        self.jsonld: list[str] = []
        self._in_jsonld = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr = dict(attrs)
        if tag == "meta" and (key := attr.get("property") or attr.get("name")):
            self.meta.setdefault(key, []).append(attr.get("content") or "")
        elif tag == "link" and attr.get("rel") == "canonical":
            self.canonical = attr.get("href")
        elif tag == "script" and attr.get("type") == "application/ld+json":
            self._in_jsonld = True
            self.jsonld.append("")

    def handle_endtag(self, tag: str) -> None:
        if tag == "script":
            self._in_jsonld = False

    def handle_data(self, data: str) -> None:
        if self._in_jsonld:
            self.jsonld[-1] += data


def ancestors(cls: str) -> set[str]:
    seen, todo = set(), [cls]
    while todo:
        if (c := todo.pop()) not in seen:
            seen.add(c)
            todo.extend(CLASSES.get(c, []))
    return seen


def check_og(head: Head) -> list[str]:
    errors = []
    one = lambda key: (head.meta.get(key) or [None])[0]
    for key in OG_REQUIRED:
        if not one(key):
            errors.append(f"missing {key}")
    for key, values in head.meta.items():
        if key.startswith(("og:", "twitter:")) and len(values) > 1 and not key.startswith("og:image"):
            errors.append(f"{key} given {len(values)} times")
    if (t := one("og:type")) and t not in OG_TYPES:
        errors.append(f"og:type {t!r} is not an Open Graph type")
    for key in ("og:url", "og:image", "twitter:image"):
        if (v := one(key)) and not ABSOLUTE.match(v):
            errors.append(f"{key} {v!r} is not an absolute https URL")
    if (url := one("og:url")) and head.canonical and url != head.canonical:
        errors.append(f"og:url {url!r} differs from canonical {head.canonical!r}")
    for key in ("og:image:width", "og:image:height"):
        if (v := one(key)) and not v.isdigit():
            errors.append(f"{key} {v!r} is not an integer")
    if (v := one("og:locale")) and not re.fullmatch(r"[a-z]{2}_[A-Z]{2}", v):
        errors.append(f"og:locale {v!r} is not language_TERRITORY")
    if (card := one("twitter:card")) and card not in TWITTER_CARDS:
        errors.append(f"twitter:card {card!r} is not a card type")
    if (v := one("twitter:creator")) and not v.startswith("@"):
        errors.append(f"twitter:creator {v!r} does not start with @")
    return errors


def check_node(node: object, path: str, ids: set[str], refs: list[tuple[str, str]], errors: list[str]) -> None:
    if isinstance(node, list):
        for i, item in enumerate(node):
            check_node(item, f"{path}[{i}]", ids, refs, errors)
        return
    if not isinstance(node, dict):
        return
    if set(node) == {"@id"}:
        refs.append((path, node["@id"]))
        return
    if "@id" in node:
        ids.add(node["@id"])
    types = node.get("@type", [])
    types = [types] if isinstance(types, str) else types
    allowed: set[str] = set()
    for t in types:
        if t not in CLASSES:
            errors.append(f"{path}: @type {t!r} is not a schema.org class")
        allowed |= ancestors(t)
    for key, value in node.items():
        if key.startswith("@"):
            continue
        if key not in PROPERTIES:
            errors.append(f"{path}: {key!r} is not a schema.org property")
        elif types and all(t in CLASSES for t in types) and not allowed & set(PROPERTIES[key]):
            errors.append(f"{path}: {key!r} does not apply to {'/'.join(types)}")
        check_node(value, f"{path}.{key}", ids, refs, errors)


def check_jsonld(head: Head) -> list[str]:
    errors: list[str] = []
    ids: set[str] = set()
    refs: list[tuple[str, str]] = []
    if not head.jsonld:
        return ["no JSON-LD"]
    for i, text in enumerate(head.jsonld):
        try:
            data = json.loads(text)
        except json.JSONDecodeError as e:
            errors.append(f"JSON-LD block {i}: {e}")
            continue
        if data.get("@context") not in ("https://schema.org", "https://schema.org/"):
            errors.append(f"JSON-LD block {i}: @context is not https://schema.org")
        check_node(data.get("@graph", data), f"block{i}", ids, refs, errors)
    errors += [f"{path}: @id {ref!r} is not defined on the page" for path, ref in refs if ref not in ids]
    return errors


def main(paths: list[str]) -> int:
    failed = False
    for path in paths:
        head = Head()
        head.feed(Path(path).read_text())
        for error in check_og(head) + check_jsonld(head):
            print(f"{path}: {error}")
            failed = True
    return int(failed)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
